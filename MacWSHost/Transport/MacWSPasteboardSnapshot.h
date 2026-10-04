#import <Foundation/Foundation.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>

// Metadata is captured by UIKit on the main queue. Providers resolve promised
// content asynchronously, so a slow producer cannot stop Host scene delivery.
static void MacWSLoadPasteboardSnapshot(
    NSArray<NSItemProvider *> *providers, NSTimeInterval timeout,
    void (^completion)(NSArray<NSDictionary *> *, NSError *)) {
    dispatch_group_t group = dispatch_group_create();
    dispatch_queue_t results = dispatch_queue_create(
        "com.macwsguide.host.pasteboard-snapshot", DISPATCH_QUEUE_SERIAL);
    NSMutableArray<NSMutableDictionary *> *items = [NSMutableArray array];
    __block NSError *failure = nil;
    __block BOOL finished = NO;
    for (NSItemProvider *provider in providers) {
        NSMutableDictionary *item = [NSMutableDictionary dictionary];
        [items addObject:item];
        for (NSString *type in provider.registeredTypeIdentifiers) {
            dispatch_group_enter(group);
            // Promised text may be returned as a callback-scoped file URL
            // by loadItem. Resolve its data representation while the provider
            // owns that file, so text does not become an imported file path.
            void (^resolved)(id<NSSecureCoding>, NSError *) =
                ^(id<NSSecureCoding> value, NSError *error) {
                    dispatch_async(results, ^{
                        if (error || !value) {
                            if (!failure) failure = error ?: [NSError
                                errorWithDomain:@"MacWSPasteboardSnapshot" code:1
                                userInfo:@{NSLocalizedDescriptionKey:
                                    @"剪贴板提供者未返回内容"}];
                        } else item[type] = value;
                        dispatch_group_leave(group);
                    });
                };
            if ([[UTType typeWithIdentifier:type] conformsToType:UTTypeText]) {
                [provider loadDataRepresentationForTypeIdentifier:type
                    completionHandler:^(NSData *data, NSError *error) {
                        resolved(data, error);
                    }];
            } else {
                [provider loadItemForTypeIdentifier:type options:nil
                    completionHandler:resolved];
            }
        }
    }
    dispatch_group_notify(group, results, ^{
        if (finished) return;
        finished = YES;
        NSMutableArray *snapshot = [NSMutableArray array];
        for (NSDictionary *item in items) [snapshot addObject:[item copy]];
        NSError *error = failure;
        dispatch_async(dispatch_get_main_queue(), ^{
            completion(error ? nil : snapshot, error);
        });
    });
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW,
        (int64_t)(timeout * NSEC_PER_SEC)), results, ^{
        if (finished) return;
        finished = YES;
        NSError *error = [NSError errorWithDomain:@"MacWSPasteboardSnapshot"
            code:2 userInfo:@{NSLocalizedDescriptionKey:
                @"剪贴板提供者读取超时，保留现有剪贴板"}];
        dispatch_async(dispatch_get_main_queue(), ^{ completion(nil, error); });
    });
}
