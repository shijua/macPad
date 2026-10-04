from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
class MachineArchitecture(unittest.TestCase):
    def test_darwin_read_contract(self):
        source = r'''
#include "macws_machine_architecture.h"
#include <assert.h>
int main(void) {
 int mib[] = {CTL_HW, HW_MACHINE}; int result=99; size_t n=0;
 assert(MacWSReadMachineArchitecture(mib,2,NULL,&n,NULL,0,&result));
 assert(n==6 && result==0);
 char data[10]; memset(data,'X',sizeof(data)); n=3;
 assert(MacWSReadMachineArchitecture(mib,2,data,&n,NULL,0,&result));
 assert(result==-1 && errno==ENOMEM && n==0 && data[0]=='X');
 n=sizeof(data);
 assert(MacWSReadMachineArchitecture(mib,2,data,&n,NULL,0,&result));
 assert(result==0 && n==6 && !strcmp(data,"arm64") && data[6]=='X');
 assert(!MacWSReadMachineArchitecture(mib,2,data,&n,"x",1,&result));
 assert(!MacWSReadMachineArchitecture(mib,2,data,NULL,NULL,0,&result));
 mib[1]=HW_MODEL;
 assert(!MacWSReadMachineArchitecture(mib,2,data,&n,NULL,0,&result));
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            binary=Path(directory)/'probe'
            subprocess.run(['clang','-x','c','-','-I',str(ROOT/'include'),'-o',str(binary)],input=source,text=True,check=True,capture_output=True)
            subprocess.run([str(binary)],check=True)
if __name__ == '__main__':unittest.main()
