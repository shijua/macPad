// Sonoma libquarantine identity ABI, RE-confirmed at 0x18c189a10..0x18c189ba4.
// Replace only missing Quarantine-policy reads, using the live kernel identity.
#include <mach/mach.h>
#include <mach-o/loader.h>
#include <mach-o/dyld_images.h>
#include <dlfcn.h>
#include <errno.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <CydiaSubstrate/CydiaSubstrate.h>

extern int proc_pidpath(int, void *, unsigned);
extern int csops_audittoken(pid_t, unsigned, void *, size_t, audit_token_t *);
extern const char *getprogname(void);
// XNU bsd/sys/codesign.h read operations; never use SET_STATUS here.
enum { Status=0, CDHash=5, SliceOffset=6, Entitlements=7, Identity=11, TeamID=14 };
struct MacWSIdentity {
    unsigned char user_uuid[16];
    char *path, *team, *signing;
    void *entitlements;
    char *hosted_path, *hosted_team;
    void *persistent_identifier;
    uint32_t platform, sdk;
    uint64_t csflags, platform_flags, binary_offset, entitlement_size;
};
_Static_assert(sizeof(struct MacWSIdentity)==0x70, "Sonoma identity size");
_Static_assert(offsetof(struct MacWSIdentity, entitlements)==0x28, "entitlement slot");
_Static_assert(offsetof(struct MacWSIdentity, platform)==0x48, "platform slot");
_Static_assert(offsetof(struct MacWSIdentity, entitlement_size)==0x68, "entitlement length");

static void *(*original_attribution)(const audit_token_t *, unsigned);

static int read_task(mach_port_t task, uint64_t address, void *buffer, size_t size) {
    vm_size_t copied=0;
    return vm_read_overwrite(task,address,size,(vm_address_t)buffer,&copied)==KERN_SUCCESS && copied==size;
}

static int live_build(mach_port_t task, uint32_t *platform, uint32_t *sdk) {
    struct task_dyld_info info={0};
    mach_msg_type_number_t count=TASK_DYLD_INFO_COUNT;
    if(task_info(task,TASK_DYLD_INFO,(task_info_t)&info,&count)!=KERN_SUCCESS) return 0;
    struct { uint32_t version,count; uint64_t array; } images={0};
    uint64_t main_image=0;
    struct mach_header_64 header={0};
    if(!read_task(task,info.all_image_info_addr,&images,sizeof(images)) || !images.count ||
       !read_task(task,images.array,&main_image,sizeof(main_image)) ||
       !read_task(task,main_image,&header,sizeof(header)) || header.magic!=MH_MAGIC_64 ||
       header.sizeofcmds>65536 || header.sizeofcmds<8) return 0;
    unsigned char *commands=malloc(header.sizeofcmds);
    if(!commands) return 0;
    int found=0;
    if(read_task(task,main_image+sizeof(header),commands,header.sizeofcmds)) {
        size_t offset=0;
        for(unsigned i=0;i<header.ncmds && offset+8<=header.sizeofcmds;i++) {
            struct load_command *command=(void *)(commands+offset);
            if(command->cmdsize<8 || command->cmdsize>header.sizeofcmds-offset) break;
            if(command->cmd==LC_BUILD_VERSION && command->cmdsize>=sizeof(struct build_version_command)) {
                struct build_version_command *build=(void *)command;
                *platform=build->platform; *sdk=build->sdk; found=1; break;
            }
            if(command->cmd==LC_VERSION_MIN_MACOSX && command->cmdsize>=sizeof(struct version_min_command)) {
                *platform=PLATFORM_MACOS; *sdk=((struct version_min_command *)command)->sdk; found=1; break;
            }
            offset+=command->cmdsize;
        }
    }
    free(commands);
    return found;
}

static uint32_t blob_length(const unsigned char *buffer) {
    return ((uint32_t)buffer[4]<<24)|((uint32_t)buffer[5]<<16)|((uint32_t)buffer[6]<<8)|buffer[7];
}

static size_t read_blob(audit_token_t *token, unsigned operation, unsigned char *buffer, size_t capacity, int optional) {
    if(csops_audittoken((pid_t)token->val[5],operation,buffer,capacity,token)!=0) {
        return optional && errno==ENOENT ? 0 : SIZE_MAX;
    }
    uint32_t size=blob_length(buffer);
    if(size<8 || size>capacity) { errno=EINVAL; return SIZE_MAX; }
    return size-8;
}

static void *macws_attribution(const audit_token_t *source, unsigned flags) {
    void *existing=original_attribution(source,flags);
    int saved_errno=errno;
    if(existing || saved_errno!=ENOPOLICY || !source || flags || !source->val[5]) return existing;
    int stage=1;
    audit_token_t token=*source, actual={{0}};
    mach_port_t task=MACH_PORT_NULL;
    mach_msg_type_number_t count=TASK_AUDIT_TOKEN_COUNT;
    uint32_t platform=0,sdk=0,csflags=0;
    uint64_t slice_offset=0;
    char path[4096]={0};
    const char *root="/private/var/mnt/rootfs";
    const char *binary_path=NULL;
    if(task_for_pid(mach_task_self(),(pid_t)token.val[5],&task)!=KERN_SUCCESS) goto failure;
    stage=2;
    if(task_info(task,TASK_AUDIT_TOKEN,(task_info_t)&actual,&count)!=KERN_SUCCESS ||
       count!=TASK_AUDIT_TOKEN_COUNT || memcmp(&actual,&token,sizeof(token)) ||
       !live_build(task,&platform,&sdk)) goto failure;
    mach_port_deallocate(mach_task_self(),task); task=MACH_PORT_NULL;
    stage=3;
    if(proc_pidpath((int)token.val[5],path,sizeof(path))<=0 ||
       path[0]!='/' || platform!=PLATFORM_MACOS) goto failure;
    // Runtime-confirmed: native proc_pidpath returns /private/var/mnt/rootfs/…;
    // the same call inside chroot returns /System/Applications/Photos.app/….
    binary_path=!strncmp(path,root,strlen(root)) && path[strlen(root)]=='/'
        ? path+strlen(root) : path;
    stage=4;
    if(csops_audittoken((pid_t)token.val[5],Status,&csflags,sizeof(csflags),&token) ||
       csops_audittoken((pid_t)token.val[5],SliceOffset,&slice_offset,sizeof(slice_offset),&token)) goto failure;
    stage=5;
    unsigned char signing[4096]={0},team[256]={0};
    unsigned char *entitlements=malloc(65536);
    if(!entitlements) goto failure;
    size_t signing_size=read_blob(&token,Identity,signing,sizeof(signing),0);
    size_t team_size=read_blob(&token,TeamID,team,sizeof(team),1);
    size_t entitlement_size=read_blob(&token,Entitlements,entitlements,65536,1);
    if(signing_size==SIZE_MAX || !signing_size || team_size==SIZE_MAX || entitlement_size==SIZE_MAX ||
       !memchr(signing+8,0,signing_size) || (team_size && !memchr(team+8,0,team_size))) {
        free(entitlements); goto failure;
    }
    size_t path_size=strlen(binary_path)+1;
    struct MacWSIdentity *identity=calloc(1,sizeof(*identity)+path_size+signing_size+team_size+entitlement_size);
    if(!identity) { free(entitlements); goto failure; }
    char *cursor=(char *)(identity+1);
    identity->path=cursor; memcpy(cursor,binary_path,path_size); cursor+=path_size;
    identity->signing=cursor; memcpy(cursor,signing+8,signing_size); cursor+=signing_size;
    if(team_size) { identity->team=cursor; memcpy(cursor,team+8,team_size); cursor+=team_size; }
    if(entitlement_size) { identity->entitlements=cursor; memcpy(cursor,entitlements+8,entitlement_size); }
    free(entitlements);
    identity->platform=platform; identity->sdk=sdk; identity->csflags=csflags;
    identity->platform_flags=(csflags&0x04000000u)?1:0;
    identity->binary_offset=slice_offset; identity->entitlement_size=entitlement_size;
    // No hosted code or persistent/user UUID is supplied by this kernel API.
    // TCCDAttributionIdentity uses the binary fields above (tccd+0x28600..0x28804).
    fprintf(stderr,"TCC live-identity pid=%u version=%u platform=%u entitlement-bytes=%zu\n",
            token.val[5],token.val[7],platform,entitlement_size);
    errno=0;
    return identity;
failure:
    if(getenv("MACWS_RESPONSIBILITY_TRACE"))
        fprintf(stderr,"TCC live-identity failure pid=%u stage=%d errno=%d\n",token.val[5],stage,errno);
    if(task!=MACH_PORT_NULL) mach_port_deallocate(mach_task_self(),task);
    errno=saved_errno;
    return NULL;
}

void MacWSInstallResponsibilityIdentity(void) {
    const char *program=getprogname();
    if(!program || strcmp(program,"tccd") || original_attribution) return;
    void *target=dlsym(RTLD_DEFAULT,"responsibility_get_attribution_for_audittoken");
    if(target) {
        MSHookFunction(target,(void *)macws_attribution,(void **)&original_attribution);
        if(getenv("MACWS_RESPONSIBILITY_TRACE"))
            fprintf(stderr,"TCC live-identity adapter installed=%d\n",original_attribution!=NULL);
    }
}
