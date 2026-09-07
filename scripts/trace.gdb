set pagination off
set confirm off
target remote localhost:2345
dprintf *0x088007b4,"CHS win=%08x code=%04x tm=%d fn=%d tpl=%08x tloff=%d curX=%d curY=%d\n",(unsigned)$r0,((unsigned)$r1)&0xffff,(unsigned)*(unsigned char*)((char*)$r0+10),(unsigned)*(unsigned char*)((char*)$r0+11),*(unsigned int*)((char*)$r0),(unsigned)*(unsigned short*)((char*)$r0+24),(unsigned)*(unsigned char*)((char*)$r0+27),(unsigned)*(unsigned char*)((char*)$r0+29)
continue
