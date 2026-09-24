
configs/POKEMON_RUBY_AXVJ00/hook/out/game.elf:     file format elf32-littlearm


Disassembly of section .text:

08800000 <EngineEntry>:
 8800000:	4900      	ldr	r1, [pc, #0]	@ (8800004 <EngineEntry+0x4>)
 8800002:	4708      	bx	r1
 8800004:	08800c15 	.word	0x08800c15

08800008 <PrintNextChar_Origin>:
 8800008:	b510      	push	{r4, lr}
 880000a:	1c04      	adds	r4, r0, #0
 880000c:	8aa0      	ldrh	r0, [r4, #20]
 880000e:	1c41      	adds	r1, r0, #1
 8800010:	4a00      	ldr	r2, [pc, #0]	@ (8800014 <PrintNextChar_Origin+0xc>)
 8800012:	4710      	bx	r2
 8800014:	08003301 	.word	0x08003301

08800018 <UpdateTilemap_Origin>:
 8800018:	4b00      	ldr	r3, [pc, #0]	@ (880001c <UpdateTilemap_Origin+0x4>)
 880001a:	4718      	bx	r3
 880001c:	080036dd 	.word	0x080036dd

08800020 <InitTextPrinter_Hook>:
 8800020:	464e      	mov	r6, r9
 8800022:	4645      	mov	r5, r8
 8800024:	b460      	push	{r5, r6}
 8800026:	b40f      	push	{r0, r1, r2, r3}
 8800028:	9c0a      	ldr	r4, [sp, #40]	@ 0x28
 880002a:	1c11      	adds	r1, r2, #0
 880002c:	1c1a      	adds	r2, r3, #0
 880002e:	1c23      	adds	r3, r4, #0
 8800030:	f000 f826 	bl	8800080 <InitTextPrinter_hook_C>
 8800034:	bc0f      	pop	{r0, r1, r2, r3}
 8800036:	9c06      	ldr	r4, [sp, #24]
 8800038:	46a1      	mov	r9, r4
 880003a:	4d01      	ldr	r5, [pc, #4]	@ (8800040 <InitTextPrinter_Hook+0x20>)
 880003c:	4728      	bx	r5
 880003e:	0000      	.short	0x0000
 8800040:	08002c75 	.word	0x08002c75

08800044 <MapName_DisplayCellLength>:
 8800044:	b501      	push	{r0, lr}
 8800046:	f001 fe75 	bl	8801d34 <MapNamePopup_CalcLeftPx>
 880004a:	1c02      	adds	r2, r0, #0
 880004c:	bc09      	pop	{r0, r3}
 880004e:	2101      	movs	r1, #1
 8800050:	1889      	adds	r1, r1, r2
 8800052:	4b01      	ldr	r3, [pc, #4]	@ (8800058 <MapName_DisplayCellLength+0x14>)
 8800054:	4718      	bx	r3
 8800056:	0000      	.short	0x0000
 8800058:	0809f6cf 	.word	0x0809f6cf

0880005c <HealthboxNickCpusetCtrl_Entry>:
 880005c:	b500      	push	{lr}
 880005e:	f001 fe7b 	bl	8801d58 <HealthboxNickCpusetCtrl>
 8800062:	bc02      	pop	{r1}
 8800064:	4708      	bx	r1
 8800066:	46c0      	nop			@ (mov r8, r8)

08800068 <UnusedPrintMonName_Hook>:
 8800068:	b500      	push	{lr}
 880006a:	f001 fea3 	bl	8801db4 <UnusedPrintMonName_hook_C>
 880006e:	bc02      	pop	{r1}
 8800070:	4708      	bx	r1
 8800072:	46c0      	nop			@ (mov r8, r8)

08800074 <DrawOptionMenuChoice_Hook>:
 8800074:	bc08      	pop	{r3}
 8800076:	b500      	push	{lr}
 8800078:	f001 ff84 	bl	8801f84 <DrawOptionMenuChoice_hook_C>
 880007c:	bc02      	pop	{r1}
 880007e:	4708      	bx	r1

08800080 <InitTextPrinter_hook_C>:
 8800080:	b510      	push	{r4, lr}
 8800082:	000c      	movs	r4, r1
 8800084:	2800      	cmp	r0, #0
 8800086:	d001      	beq.n	880008c <InitTextPrinter_hook_C+0xc>
 8800088:	f000 ff96 	bl	8800fb8 <v8_phase_reset>
 880008c:	0020      	movs	r0, r4
 880008e:	bc10      	pop	{r4}
 8800090:	bc02      	pop	{r1}
 8800092:	4708      	bx	r1

08800094 <chs_slot_for>:
 8800094:	b5f0      	push	{r4, r5, r6, r7, lr}
 8800096:	46ce      	mov	lr, r9
 8800098:	4647      	mov	r7, r8
 880009a:	468c      	mov	ip, r1
 880009c:	b580      	push	{r7, lr}
 880009e:	2800      	cmp	r0, #0
 88000a0:	d100      	bne.n	88000a4 <chs_slot_for+0x10>
 88000a2:	e085      	b.n	88001b0 <chs_slot_for+0x11c>
 88000a4:	4b46      	ldr	r3, [pc, #280]	@ (88001c0 <chs_slot_for+0x12c>)
 88000a6:	255c      	movs	r5, #92	@ 0x5c
 88000a8:	4698      	mov	r8, r3
 88000aa:	4e46      	ldr	r6, [pc, #280]	@ (88001c4 <chs_slot_for+0x130>)
 88000ac:	4b46      	ldr	r3, [pc, #280]	@ (88001c8 <chs_slot_for+0x134>)
 88000ae:	6819      	ldr	r1, [r3, #0]
 88000b0:	4b46      	ldr	r3, [pc, #280]	@ (88001cc <chs_slot_for+0x138>)
 88000b2:	4299      	cmp	r1, r3
 88000b4:	d01a      	beq.n	88000ec <chs_slot_for+0x58>
 88000b6:	4c46      	ldr	r4, [pc, #280]	@ (88001d0 <chs_slot_for+0x13c>)
 88000b8:	2000      	movs	r0, #0
 88000ba:	0027      	movs	r7, r4
 88000bc:	4b45      	ldr	r3, [pc, #276]	@ (88001d4 <chs_slot_for+0x140>)
 88000be:	218a      	movs	r1, #138	@ 0x8a
 88000c0:	00c9      	lsls	r1, r1, #3
 88000c2:	1859      	adds	r1, r3, r1
 88000c4:	6018      	str	r0, [r3, #0]
 88000c6:	6058      	str	r0, [r3, #4]
 88000c8:	6008      	str	r0, [r1, #0]
 88000ca:	4943      	ldr	r1, [pc, #268]	@ (88001d8 <chs_slot_for+0x144>)
 88000cc:	1859      	adds	r1, r3, r1
 88000ce:	6008      	str	r0, [r1, #0]
 88000d0:	218a      	movs	r1, #138	@ 0x8a
 88000d2:	00c9      	lsls	r1, r1, #3
 88000d4:	1861      	adds	r1, r4, r1
 88000d6:	3308      	adds	r3, #8
 88000d8:	6020      	str	r0, [r4, #0]
 88000da:	6008      	str	r0, [r1, #0]
 88000dc:	3404      	adds	r4, #4
 88000de:	42bb      	cmp	r3, r7
 88000e0:	d1ed      	bne.n	88000be <chs_slot_for+0x2a>
 88000e2:	4b3e      	ldr	r3, [pc, #248]	@ (88001dc <chs_slot_for+0x148>)
 88000e4:	4939      	ldr	r1, [pc, #228]	@ (88001cc <chs_slot_for+0x138>)
 88000e6:	6018      	str	r0, [r3, #0]
 88000e8:	4b37      	ldr	r3, [pc, #220]	@ (88001c8 <chs_slot_for+0x134>)
 88000ea:	6019      	str	r1, [r3, #0]
 88000ec:	4661      	mov	r1, ip
 88000ee:	2900      	cmp	r1, #0
 88000f0:	d100      	bne.n	88000f4 <chs_slot_for+0x60>
 88000f2:	3101      	adds	r1, #1
 88000f4:	4b39      	ldr	r3, [pc, #228]	@ (88001dc <chs_slot_for+0x148>)
 88000f6:	681b      	ldr	r3, [r3, #0]
 88000f8:	3301      	adds	r3, #1
 88000fa:	469c      	mov	ip, r3
 88000fc:	23f0      	movs	r3, #240	@ 0xf0
 88000fe:	061b      	lsls	r3, r3, #24
 8800100:	459c      	cmp	ip, r3
 8800102:	d310      	bcc.n	8800126 <chs_slot_for+0x92>
 8800104:	4b32      	ldr	r3, [pc, #200]	@ (88001d0 <chs_slot_for+0x13c>)
 8800106:	4f2f      	ldr	r7, [pc, #188]	@ (88001c4 <chs_slot_for+0x130>)
 8800108:	6818      	ldr	r0, [r3, #0]
 880010a:	0840      	lsrs	r0, r0, #1
 880010c:	6018      	str	r0, [r3, #0]
 880010e:	208a      	movs	r0, #138	@ 0x8a
 8800110:	00c0      	lsls	r0, r0, #3
 8800112:	181c      	adds	r4, r3, r0
 8800114:	6820      	ldr	r0, [r4, #0]
 8800116:	3304      	adds	r3, #4
 8800118:	0840      	lsrs	r0, r0, #1
 880011a:	6020      	str	r0, [r4, #0]
 880011c:	42bb      	cmp	r3, r7
 880011e:	d1f3      	bne.n	8800108 <chs_slot_for+0x74>
 8800120:	23f0      	movs	r3, #240	@ 0xf0
 8800122:	05db      	lsls	r3, r3, #23
 8800124:	469c      	mov	ip, r3
 8800126:	4660      	mov	r0, ip
 8800128:	4b2c      	ldr	r3, [pc, #176]	@ (88001dc <chs_slot_for+0x148>)
 880012a:	0037      	movs	r7, r6
 880012c:	6018      	str	r0, [r3, #0]
 880012e:	2400      	movs	r4, #0
 8800130:	0030      	movs	r0, r6
 8800132:	e005      	b.n	8800140 <chs_slot_for+0xac>
 8800134:	3401      	adds	r4, #1
 8800136:	0423      	lsls	r3, r4, #16
 8800138:	3008      	adds	r0, #8
 880013a:	0c1b      	lsrs	r3, r3, #16
 880013c:	429d      	cmp	r5, r3
 880013e:	d90c      	bls.n	880015a <chs_slot_for+0xc6>
 8800140:	6803      	ldr	r3, [r0, #0]
 8800142:	428b      	cmp	r3, r1
 8800144:	d1f6      	bne.n	8800134 <chs_slot_for+0xa0>
 8800146:	6843      	ldr	r3, [r0, #4]
 8800148:	4293      	cmp	r3, r2
 880014a:	d1f3      	bne.n	8800134 <chs_slot_for+0xa0>
 880014c:	4663      	mov	r3, ip
 880014e:	0420      	lsls	r0, r4, #16
 8800150:	00a4      	lsls	r4, r4, #2
 8800152:	4444      	add	r4, r8
 8800154:	6023      	str	r3, [r4, #0]
 8800156:	0c00      	lsrs	r0, r0, #16
 8800158:	e024      	b.n	88001a4 <chs_slot_for+0x110>
 880015a:	2000      	movs	r0, #0
 880015c:	683b      	ldr	r3, [r7, #0]
 880015e:	2b00      	cmp	r3, #0
 8800160:	d02b      	beq.n	88001ba <chs_slot_for+0x126>
 8800162:	3001      	adds	r0, #1
 8800164:	0400      	lsls	r0, r0, #16
 8800166:	0c00      	lsrs	r0, r0, #16
 8800168:	3708      	adds	r7, #8
 880016a:	42a8      	cmp	r0, r5
 880016c:	d1f6      	bne.n	880015c <chs_slot_for+0xc8>
 880016e:	4644      	mov	r4, r8
 8800170:	cc08      	ldmia	r4!, {r3}
 8800172:	2000      	movs	r0, #0
 8800174:	4699      	mov	r9, r3
 8800176:	2301      	movs	r3, #1
 8800178:	6827      	ldr	r7, [r4, #0]
 880017a:	454f      	cmp	r7, r9
 880017c:	d202      	bcs.n	8800184 <chs_slot_for+0xf0>
 880017e:	6820      	ldr	r0, [r4, #0]
 8800180:	4681      	mov	r9, r0
 8800182:	0018      	movs	r0, r3
 8800184:	3301      	adds	r3, #1
 8800186:	041b      	lsls	r3, r3, #16
 8800188:	0c1b      	lsrs	r3, r3, #16
 880018a:	3404      	adds	r4, #4
 880018c:	42ab      	cmp	r3, r5
 880018e:	d1f3      	bne.n	8800178 <chs_slot_for+0xe4>
 8800190:	00c3      	lsls	r3, r0, #3
 8800192:	18f4      	adds	r4, r6, r3
 8800194:	18f6      	adds	r6, r6, r3
 8800196:	0083      	lsls	r3, r0, #2
 8800198:	4443      	add	r3, r8
 880019a:	001f      	movs	r7, r3
 880019c:	4663      	mov	r3, ip
 880019e:	6021      	str	r1, [r4, #0]
 88001a0:	6072      	str	r2, [r6, #4]
 88001a2:	603b      	str	r3, [r7, #0]
 88001a4:	bcc0      	pop	{r6, r7}
 88001a6:	46b9      	mov	r9, r7
 88001a8:	46b0      	mov	r8, r6
 88001aa:	bcf0      	pop	{r4, r5, r6, r7}
 88001ac:	bc02      	pop	{r1}
 88001ae:	4708      	bx	r1
 88001b0:	4b07      	ldr	r3, [pc, #28]	@ (88001d0 <chs_slot_for+0x13c>)
 88001b2:	2528      	movs	r5, #40	@ 0x28
 88001b4:	4698      	mov	r8, r3
 88001b6:	4e07      	ldr	r6, [pc, #28]	@ (88001d4 <chs_slot_for+0x140>)
 88001b8:	e778      	b.n	88000ac <chs_slot_for+0x18>
 88001ba:	4285      	cmp	r5, r0
 88001bc:	d1e8      	bne.n	8800190 <chs_slot_for+0xfc>
 88001be:	e7d6      	b.n	880016e <chs_slot_for+0xda>
 88001c0:	0203e738 	.word	0x0203e738
 88001c4:	0203e458 	.word	0x0203e458
 88001c8:	0203e000 	.word	0x0203e000
 88001cc:	4232544c 	.word	0x4232544c
 88001d0:	0203e2e8 	.word	0x0203e2e8
 88001d4:	0203e008 	.word	0x0203e008
 88001d8:	00000454 	.word	0x00000454
 88001dc:	0203e004 	.word	0x0203e004

088001e0 <resolve_draw>:
 88001e0:	b570      	push	{r4, r5, r6, lr}
 88001e2:	0004      	movs	r4, r0
 88001e4:	7a85      	ldrb	r5, [r0, #10]
 88001e6:	2007      	movs	r0, #7
 88001e8:	4028      	ands	r0, r5
 88001ea:	7ae5      	ldrb	r5, [r4, #11]
 88001ec:	7010      	strb	r0, [r2, #0]
 88001ee:	2d06      	cmp	r5, #6
 88001f0:	d904      	bls.n	88001fc <resolve_draw+0x1c>
 88001f2:	2802      	cmp	r0, #2
 88001f4:	d027      	beq.n	8800246 <resolve_draw+0x66>
 88001f6:	2203      	movs	r2, #3
 88001f8:	701a      	strb	r2, [r3, #0]
 88001fa:	e004      	b.n	8800206 <resolve_draw+0x26>
 88001fc:	2802      	cmp	r0, #2
 88001fe:	d022      	beq.n	8800246 <resolve_draw+0x66>
 8800200:	701d      	strb	r5, [r3, #0]
 8800202:	2d04      	cmp	r5, #4
 8800204:	d021      	beq.n	880024a <resolve_draw+0x6a>
 8800206:	2908      	cmp	r1, #8
 8800208:	d01f      	beq.n	880024a <resolve_draw+0x6a>
 880020a:	7861      	ldrb	r1, [r4, #1]
 880020c:	7823      	ldrb	r3, [r4, #0]
 880020e:	0209      	lsls	r1, r1, #8
 8800210:	4319      	orrs	r1, r3
 8800212:	78a3      	ldrb	r3, [r4, #2]
 8800214:	78e0      	ldrb	r0, [r4, #3]
 8800216:	041b      	lsls	r3, r3, #16
 8800218:	430b      	orrs	r3, r1
 880021a:	0600      	lsls	r0, r0, #24
 880021c:	0021      	movs	r1, r4
 880021e:	7ea2      	ldrb	r2, [r4, #26]
 8800220:	4318      	orrs	r0, r3
 8800222:	f001 fd4b 	bl	8801cbc <v6_scene_font>
 8800226:	280d      	cmp	r0, #13
 8800228:	d013      	beq.n	8800252 <resolve_draw+0x72>
 880022a:	280a      	cmp	r0, #10
 880022c:	d00d      	beq.n	880024a <resolve_draw+0x6a>
 880022e:	210c      	movs	r1, #12
 8800230:	220b      	movs	r2, #11
 8800232:	2301      	movs	r3, #1
 8800234:	9804      	ldr	r0, [sp, #16]
 8800236:	7001      	strb	r1, [r0, #0]
 8800238:	9905      	ldr	r1, [sp, #20]
 880023a:	700a      	strb	r2, [r1, #0]
 880023c:	9a06      	ldr	r2, [sp, #24]
 880023e:	7013      	strb	r3, [r2, #0]
 8800240:	bc70      	pop	{r4, r5, r6}
 8800242:	bc01      	pop	{r0}
 8800244:	4700      	bx	r0
 8800246:	2204      	movs	r2, #4
 8800248:	701a      	strb	r2, [r3, #0]
 880024a:	210a      	movs	r1, #10
 880024c:	2209      	movs	r2, #9
 880024e:	2303      	movs	r3, #3
 8800250:	e7f0      	b.n	8800234 <resolve_draw+0x54>
 8800252:	210a      	movs	r1, #10
 8800254:	2209      	movs	r2, #9
 8800256:	2302      	movs	r3, #2
 8800258:	e7ec      	b.n	8800234 <resolve_draw+0x54>
 880025a:	46c0      	nop			@ (mov r8, r8)

0880025c <chs_emit.isra.0>:
 880025c:	b5f0      	push	{r4, r5, r6, r7, lr}
 880025e:	4657      	mov	r7, sl
 8800260:	46de      	mov	lr, fp
 8800262:	464e      	mov	r6, r9
 8800264:	4645      	mov	r5, r8
 8800266:	b5e0      	push	{r5, r6, r7, lr}
 8800268:	b0bd      	sub	sp, #244	@ 0xf4
 880026a:	9311      	str	r3, [sp, #68]	@ 0x44
 880026c:	9b46      	ldr	r3, [sp, #280]	@ 0x118
 880026e:	468a      	mov	sl, r1
 8800270:	900e      	str	r0, [sp, #56]	@ 0x38
 8800272:	920f      	str	r2, [sp, #60]	@ 0x3c
 8800274:	2b00      	cmp	r3, #0
 8800276:	d100      	bne.n	880027a <chs_emit.isra.0+0x1e>
 8800278:	9246      	str	r2, [sp, #280]	@ 0x118
 880027a:	4653      	mov	r3, sl
 880027c:	2b02      	cmp	r3, #2
 880027e:	d100      	bne.n	8800282 <chs_emit.isra.0+0x26>
 8800280:	e1bc      	b.n	88005fc <chs_emit.isra.0+0x3a0>
 8800282:	980e      	ldr	r0, [sp, #56]	@ 0x38
 8800284:	7842      	ldrb	r2, [r0, #1]
 8800286:	7803      	ldrb	r3, [r0, #0]
 8800288:	0212      	lsls	r2, r2, #8
 880028a:	431a      	orrs	r2, r3
 880028c:	7883      	ldrb	r3, [r0, #2]
 880028e:	041b      	lsls	r3, r3, #16
 8800290:	4313      	orrs	r3, r2
 8800292:	78c2      	ldrb	r2, [r0, #3]
 8800294:	0612      	lsls	r2, r2, #24
 8800296:	431a      	orrs	r2, r3
 8800298:	4693      	mov	fp, r2
 880029a:	2607      	movs	r6, #7
 880029c:	f000 fe5c 	bl	8800f58 <v8_phase_get>
 88002a0:	9b0f      	ldr	r3, [sp, #60]	@ 0x3c
 88002a2:	4006      	ands	r6, r0
 88002a4:	199b      	adds	r3, r3, r6
 88002a6:	08db      	lsrs	r3, r3, #3
 88002a8:	9310      	str	r3, [sp, #64]	@ 0x40
 88002aa:	d01c      	beq.n	88002e6 <chs_emit.isra.0+0x8a>
 88002ac:	465b      	mov	r3, fp
 88002ae:	2b00      	cmp	r3, #0
 88002b0:	d00d      	beq.n	88002ce <chs_emit.isra.0+0x72>
 88002b2:	465a      	mov	r2, fp
 88002b4:	7b52      	ldrb	r2, [r2, #13]
 88002b6:	7b1b      	ldrb	r3, [r3, #12]
 88002b8:	0212      	lsls	r2, r2, #8
 88002ba:	431a      	orrs	r2, r3
 88002bc:	465b      	mov	r3, fp
 88002be:	7b9b      	ldrb	r3, [r3, #14]
 88002c0:	041b      	lsls	r3, r3, #16
 88002c2:	4313      	orrs	r3, r2
 88002c4:	465a      	mov	r2, fp
 88002c6:	7bd5      	ldrb	r5, [r2, #15]
 88002c8:	062d      	lsls	r5, r5, #24
 88002ca:	431d      	orrs	r5, r3
 88002cc:	d11b      	bne.n	8800306 <chs_emit.isra.0+0xaa>
 88002ce:	4653      	mov	r3, sl
 88002d0:	2b01      	cmp	r3, #1
 88002d2:	d90b      	bls.n	88002ec <chs_emit.isra.0+0x90>
 88002d4:	b03d      	add	sp, #244	@ 0xf4
 88002d6:	bcf0      	pop	{r4, r5, r6, r7}
 88002d8:	46bb      	mov	fp, r7
 88002da:	46b2      	mov	sl, r6
 88002dc:	46a9      	mov	r9, r5
 88002de:	46a0      	mov	r8, r4
 88002e0:	bcf0      	pop	{r4, r5, r6, r7}
 88002e2:	bc01      	pop	{r0}
 88002e4:	4700      	bx	r0
 88002e6:	3301      	adds	r3, #1
 88002e8:	9310      	str	r3, [sp, #64]	@ 0x40
 88002ea:	e7df      	b.n	88002ac <chs_emit.isra.0+0x50>
 88002ec:	980e      	ldr	r0, [sp, #56]	@ 0x38
 88002ee:	9b10      	ldr	r3, [sp, #64]	@ 0x40
 88002f0:	005a      	lsls	r2, r3, #1
 88002f2:	7e43      	ldrb	r3, [r0, #25]
 88002f4:	7e01      	ldrb	r1, [r0, #24]
 88002f6:	021b      	lsls	r3, r3, #8
 88002f8:	430b      	orrs	r3, r1
 88002fa:	18d3      	adds	r3, r2, r3
 88002fc:	041a      	lsls	r2, r3, #16
 88002fe:	0e12      	lsrs	r2, r2, #24
 8800300:	7603      	strb	r3, [r0, #24]
 8800302:	7642      	strb	r2, [r0, #25]
 8800304:	e7e6      	b.n	88002d4 <chs_emit.isra.0+0x78>
 8800306:	4bb9      	ldr	r3, [pc, #740]	@ (88005ec <chs_emit.isra.0+0x390>)
 8800308:	781a      	ldrb	r2, [r3, #0]
 880030a:	2a00      	cmp	r2, #0
 880030c:	d101      	bne.n	8800312 <chs_emit.isra.0+0xb6>
 880030e:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 8800310:	7b1a      	ldrb	r2, [r3, #12]
 8800312:	9c0e      	ldr	r4, [sp, #56]	@ 0x38
 8800314:	7aa3      	ldrb	r3, [r4, #10]
 8800316:	7b60      	ldrb	r0, [r4, #13]
 8800318:	9317      	str	r3, [sp, #92]	@ 0x5c
 880031a:	7ee3      	ldrb	r3, [r4, #27]
 880031c:	9313      	str	r3, [sp, #76]	@ 0x4c
 880031e:	0203      	lsls	r3, r0, #8
 8800320:	0407      	lsls	r7, r0, #16
 8800322:	4303      	orrs	r3, r0
 8800324:	433b      	orrs	r3, r7
 8800326:	0600      	lsls	r0, r0, #24
 8800328:	4303      	orrs	r3, r0
 880032a:	203e      	movs	r0, #62	@ 0x3e
 880032c:	931f      	str	r3, [sp, #124]	@ 0x7c
 880032e:	7ba1      	ldrb	r1, [r4, #14]
 8800330:	931c      	str	r3, [sp, #112]	@ 0x70
 8800332:	931d      	str	r3, [sp, #116]	@ 0x74
 8800334:	931e      	str	r3, [sp, #120]	@ 0x78
 8800336:	ab10      	add	r3, sp, #64	@ 0x40
 8800338:	181b      	adds	r3, r3, r0
 880033a:	7019      	strb	r1, [r3, #0]
 880033c:	213f      	movs	r1, #63	@ 0x3f
 880033e:	ab10      	add	r3, sp, #64	@ 0x40
 8800340:	185b      	adds	r3, r3, r1
 8800342:	701a      	strb	r2, [r3, #0]
 8800344:	22c0      	movs	r2, #192	@ 0xc0
 8800346:	0beb      	lsrs	r3, r5, #15
 8800348:	03db      	lsls	r3, r3, #15
 880034a:	04d2      	lsls	r2, r2, #19
 880034c:	4293      	cmp	r3, r2
 880034e:	d100      	bne.n	8800352 <chs_emit.isra.0+0xf6>
 8800350:	e1d3      	b.n	88006fa <chs_emit.isra.0+0x49e>
 8800352:	7de7      	ldrb	r7, [r4, #23]
 8800354:	7da3      	ldrb	r3, [r4, #22]
 8800356:	023f      	lsls	r7, r7, #8
 8800358:	431f      	orrs	r7, r3
 880035a:	2384      	movs	r3, #132	@ 0x84
 880035c:	009b      	lsls	r3, r3, #2
 880035e:	469c      	mov	ip, r3
 8800360:	2301      	movs	r3, #1
 8800362:	245c      	movs	r4, #92	@ 0x5c
 8800364:	4698      	mov	r8, r3
 8800366:	4467      	add	r7, ip
 8800368:	043f      	lsls	r7, r7, #16
 880036a:	0c3f      	lsrs	r7, r7, #16
 880036c:	9b47      	ldr	r3, [sp, #284]	@ 0x11c
 880036e:	00db      	lsls	r3, r3, #3
 8800370:	4699      	mov	r9, r3
 8800372:	2e00      	cmp	r6, #0
 8800374:	d00f      	beq.n	8800396 <chs_emit.isra.0+0x13a>
 8800376:	4b9e      	ldr	r3, [pc, #632]	@ (88005f0 <chs_emit.isra.0+0x394>)
 8800378:	980e      	ldr	r0, [sp, #56]	@ 0x38
 880037a:	f000 fca5 	bl	8800cc8 <PrintNextChar_Hook+0xb4>
 880037e:	464b      	mov	r3, r9
 8800380:	4333      	orrs	r3, r6
 8800382:	4699      	mov	r9, r3
 8800384:	2800      	cmp	r0, #0
 8800386:	d006      	beq.n	8800396 <chs_emit.isra.0+0x13a>
 8800388:	8803      	ldrh	r3, [r0, #0]
 880038a:	059b      	lsls	r3, r3, #22
 880038c:	0d9a      	lsrs	r2, r3, #22
 880038e:	9215      	str	r2, [sp, #84]	@ 0x54
 8800390:	42ba      	cmp	r2, r7
 8800392:	d300      	bcc.n	8800396 <chs_emit.isra.0+0x13a>
 8800394:	e1c3      	b.n	880071e <chs_emit.isra.0+0x4c2>
 8800396:	2300      	movs	r3, #0
 8800398:	2200      	movs	r2, #0
 880039a:	9315      	str	r3, [sp, #84]	@ 0x54
 880039c:	980e      	ldr	r0, [sp, #56]	@ 0x38
 880039e:	7843      	ldrb	r3, [r0, #1]
 88003a0:	7801      	ldrb	r1, [r0, #0]
 88003a2:	021b      	lsls	r3, r3, #8
 88003a4:	430b      	orrs	r3, r1
 88003a6:	7881      	ldrb	r1, [r0, #2]
 88003a8:	0409      	lsls	r1, r1, #16
 88003aa:	4319      	orrs	r1, r3
 88003ac:	78c3      	ldrb	r3, [r0, #3]
 88003ae:	061b      	lsls	r3, r3, #24
 88003b0:	430b      	orrs	r3, r1
 88003b2:	d100      	bne.n	88003b6 <chs_emit.isra.0+0x15a>
 88003b4:	e78b      	b.n	88002ce <chs_emit.isra.0+0x72>
 88003b6:	7b58      	ldrb	r0, [r3, #13]
 88003b8:	7b19      	ldrb	r1, [r3, #12]
 88003ba:	0200      	lsls	r0, r0, #8
 88003bc:	4308      	orrs	r0, r1
 88003be:	7b99      	ldrb	r1, [r3, #14]
 88003c0:	7bdb      	ldrb	r3, [r3, #15]
 88003c2:	0409      	lsls	r1, r1, #16
 88003c4:	4301      	orrs	r1, r0
 88003c6:	061b      	lsls	r3, r3, #24
 88003c8:	430b      	orrs	r3, r1
 88003ca:	d100      	bne.n	88003ce <chs_emit.isra.0+0x172>
 88003cc:	e77f      	b.n	88002ce <chs_emit.isra.0+0x72>
 88003ce:	21c0      	movs	r1, #192	@ 0xc0
 88003d0:	0bdb      	lsrs	r3, r3, #15
 88003d2:	03db      	lsls	r3, r3, #15
 88003d4:	04c9      	lsls	r1, r1, #19
 88003d6:	428b      	cmp	r3, r1
 88003d8:	d100      	bne.n	88003dc <chs_emit.isra.0+0x180>
 88003da:	e194      	b.n	8800706 <chs_emit.isra.0+0x4aa>
 88003dc:	990e      	ldr	r1, [sp, #56]	@ 0x38
 88003de:	7dcf      	ldrb	r7, [r1, #23]
 88003e0:	7d8b      	ldrb	r3, [r1, #22]
 88003e2:	023f      	lsls	r7, r7, #8
 88003e4:	431f      	orrs	r7, r3
 88003e6:	23e0      	movs	r3, #224	@ 0xe0
 88003e8:	009b      	lsls	r3, r3, #2
 88003ea:	18f9      	adds	r1, r7, r3
 88003ec:	3380      	adds	r3, #128	@ 0x80
 88003ee:	4299      	cmp	r1, r3
 88003f0:	d900      	bls.n	88003f4 <chs_emit.isra.0+0x198>
 88003f2:	e76c      	b.n	88002ce <chs_emit.isra.0+0x72>
 88003f4:	4649      	mov	r1, r9
 88003f6:	2001      	movs	r0, #1
 88003f8:	f7ff fe4c 	bl	8800094 <chs_slot_for>
 88003fc:	2284      	movs	r2, #132	@ 0x84
 88003fe:	0092      	lsls	r2, r2, #2
 8800400:	4694      	mov	ip, r2
 8800402:	0083      	lsls	r3, r0, #2
 8800404:	4467      	add	r7, ip
 8800406:	19db      	adds	r3, r3, r7
 8800408:	041b      	lsls	r3, r3, #16
 880040a:	0c1a      	lsrs	r2, r3, #16
 880040c:	921a      	str	r2, [sp, #104]	@ 0x68
 880040e:	2b00      	cmp	r3, #0
 8800410:	d100      	bne.n	8800414 <chs_emit.isra.0+0x1b8>
 8800412:	e75c      	b.n	88002ce <chs_emit.isra.0+0x72>
 8800414:	2308      	movs	r3, #8
 8800416:	9a46      	ldr	r2, [sp, #280]	@ 0x118
 8800418:	1b9b      	subs	r3, r3, r6
 880041a:	9312      	str	r3, [sp, #72]	@ 0x48
 880041c:	4293      	cmp	r3, r2
 880041e:	d900      	bls.n	8800422 <chs_emit.isra.0+0x1c6>
 8800420:	9212      	str	r2, [sp, #72]	@ 0x48
 8800422:	9a46      	ldr	r2, [sp, #280]	@ 0x118
 8800424:	9b12      	ldr	r3, [sp, #72]	@ 0x48
 8800426:	1ad2      	subs	r2, r2, r3
 8800428:	9214      	str	r2, [sp, #80]	@ 0x50
 880042a:	9a46      	ldr	r2, [sp, #280]	@ 0x118
 880042c:	429a      	cmp	r2, r3
 880042e:	d100      	bne.n	8800432 <chs_emit.isra.0+0x1d6>
 8800430:	e1a6      	b.n	8800780 <chs_emit.isra.0+0x524>
 8800432:	9a1a      	ldr	r2, [sp, #104]	@ 0x68
 8800434:	1c93      	adds	r3, r2, #2
 8800436:	041b      	lsls	r3, r3, #16
 8800438:	0c1b      	lsrs	r3, r3, #16
 880043a:	9316      	str	r3, [sp, #88]	@ 0x58
 880043c:	0153      	lsls	r3, r2, #5
 880043e:	9319      	str	r3, [sp, #100]	@ 0x64
 8800440:	1c53      	adds	r3, r2, #1
 8800442:	931b      	str	r3, [sp, #108]	@ 0x6c
 8800444:	015b      	lsls	r3, r3, #5
 8800446:	9318      	str	r3, [sp, #96]	@ 0x60
 8800448:	2e00      	cmp	r6, #0
 880044a:	d100      	bne.n	880044e <chs_emit.isra.0+0x1f2>
 880044c:	e1d0      	b.n	88007f0 <chs_emit.isra.0+0x594>
 880044e:	2201      	movs	r2, #1
 8800450:	9f19      	ldr	r7, [sp, #100]	@ 0x64
 8800452:	4691      	mov	r9, r2
 8800454:	003b      	movs	r3, r7
 8800456:	320e      	adds	r2, #14
 8800458:	4690      	mov	r8, r2
 880045a:	3320      	adds	r3, #32
 880045c:	2010      	movs	r0, #16
 880045e:	2100      	movs	r1, #0
 8800460:	469c      	mov	ip, r3
 8800462:	e00b      	b.n	880047c <chs_emit.isra.0+0x220>
 8800464:	4643      	mov	r3, r8
 8800466:	3101      	adds	r1, #1
 8800468:	439a      	bics	r2, r3
 880046a:	430a      	orrs	r2, r1
 880046c:	0612      	lsls	r2, r2, #24
 880046e:	3010      	adds	r0, #16
 8800470:	0e12      	lsrs	r2, r2, #24
 8800472:	0600      	lsls	r0, r0, #24
 8800474:	7022      	strb	r2, [r4, #0]
 8800476:	0e00      	lsrs	r0, r0, #24
 8800478:	428e      	cmp	r6, r1
 880047a:	d910      	bls.n	880049e <chs_emit.isra.0+0x242>
 880047c:	464b      	mov	r3, r9
 880047e:	084a      	lsrs	r2, r1, #1
 8800480:	19d2      	adds	r2, r2, r7
 8800482:	18ac      	adds	r4, r5, r2
 8800484:	5caa      	ldrb	r2, [r5, r2]
 8800486:	420b      	tst	r3, r1
 8800488:	d0ec      	beq.n	8800464 <chs_emit.isra.0+0x208>
 880048a:	4643      	mov	r3, r8
 880048c:	401a      	ands	r2, r3
 880048e:	4302      	orrs	r2, r0
 8800490:	3010      	adds	r0, #16
 8800492:	0600      	lsls	r0, r0, #24
 8800494:	3101      	adds	r1, #1
 8800496:	7022      	strb	r2, [r4, #0]
 8800498:	0e00      	lsrs	r0, r0, #24
 880049a:	428e      	cmp	r6, r1
 880049c:	d8ee      	bhi.n	880047c <chs_emit.isra.0+0x220>
 880049e:	3704      	adds	r7, #4
 88004a0:	4663      	mov	r3, ip
 88004a2:	4567      	cmp	r7, ip
 88004a4:	d1da      	bne.n	880045c <chs_emit.isra.0+0x200>
 88004a6:	2300      	movs	r3, #0
 88004a8:	469c      	mov	ip, r3
 88004aa:	3304      	adds	r3, #4
 88004ac:	4699      	mov	r9, r3
 88004ae:	9b18      	ldr	r3, [sp, #96]	@ 0x60
 88004b0:	4664      	mov	r4, ip
 88004b2:	200f      	movs	r0, #15
 88004b4:	4698      	mov	r8, r3
 88004b6:	46b4      	mov	ip, r6
 88004b8:	4662      	mov	r2, ip
 88004ba:	2100      	movs	r1, #0
 88004bc:	4646      	mov	r6, r8
 88004be:	46a4      	mov	ip, r4
 88004c0:	920d      	str	r2, [sp, #52]	@ 0x34
 88004c2:	e007      	b.n	88004d4 <chs_emit.isra.0+0x278>
 88004c4:	4383      	bics	r3, r0
 88004c6:	431a      	orrs	r2, r3
 88004c8:	4643      	mov	r3, r8
 88004ca:	701a      	strb	r2, [r3, #0]
 88004cc:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 88004ce:	3101      	adds	r1, #1
 88004d0:	428b      	cmp	r3, r1
 88004d2:	d91b      	bls.n	880050c <chs_emit.isra.0+0x2b0>
 88004d4:	4f47      	ldr	r7, [pc, #284]	@ (88005f4 <chs_emit.isra.0+0x398>)
 88004d6:	46b8      	mov	r8, r7
 88004d8:	464c      	mov	r4, r9
 88004da:	084b      	lsrs	r3, r1, #1
 88004dc:	4463      	add	r3, ip
 88004de:	18ea      	adds	r2, r5, r3
 88004e0:	4442      	add	r2, r8
 88004e2:	18f3      	adds	r3, r6, r3
 88004e4:	7812      	ldrb	r2, [r2, #0]
 88004e6:	008f      	lsls	r7, r1, #2
 88004e8:	4027      	ands	r7, r4
 88004ea:	18ec      	adds	r4, r5, r3
 88004ec:	413a      	asrs	r2, r7
 88004ee:	46a0      	mov	r8, r4
 88004f0:	2401      	movs	r4, #1
 88004f2:	5ceb      	ldrb	r3, [r5, r3]
 88004f4:	4002      	ands	r2, r0
 88004f6:	420c      	tst	r4, r1
 88004f8:	d0e4      	beq.n	88004c4 <chs_emit.isra.0+0x268>
 88004fa:	4003      	ands	r3, r0
 88004fc:	0112      	lsls	r2, r2, #4
 88004fe:	431a      	orrs	r2, r3
 8800500:	4643      	mov	r3, r8
 8800502:	701a      	strb	r2, [r3, #0]
 8800504:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 8800506:	3101      	adds	r1, #1
 8800508:	428b      	cmp	r3, r1
 880050a:	d8e3      	bhi.n	88004d4 <chs_emit.isra.0+0x278>
 880050c:	4664      	mov	r4, ip
 880050e:	3404      	adds	r4, #4
 8800510:	46b0      	mov	r8, r6
 8800512:	469c      	mov	ip, r3
 8800514:	2c20      	cmp	r4, #32
 8800516:	d1cf      	bne.n	88004b8 <chs_emit.isra.0+0x25c>
 8800518:	001e      	movs	r6, r3
 880051a:	ab24      	add	r3, sp, #144	@ 0x90
 880051c:	4699      	mov	r9, r3
 880051e:	ab2c      	add	r3, sp, #176	@ 0xb0
 8800520:	4698      	mov	r8, r3
 8800522:	9c12      	ldr	r4, [sp, #72]	@ 0x48
 8800524:	2100      	movs	r1, #0
 8800526:	0022      	movs	r2, r4
 8800528:	9300      	str	r3, [sp, #0]
 880052a:	9811      	ldr	r0, [sp, #68]	@ 0x44
 880052c:	464b      	mov	r3, r9
 880052e:	f000 fc89 	bl	8800e44 <extract_cols>
 8800532:	9b19      	ldr	r3, [sp, #100]	@ 0x64
 8800534:	18e8      	adds	r0, r5, r3
 8800536:	ab1c      	add	r3, sp, #112	@ 0x70
 8800538:	464a      	mov	r2, r9
 880053a:	2100      	movs	r1, #0
 880053c:	9301      	str	r3, [sp, #4]
 880053e:	9600      	str	r6, [sp, #0]
 8800540:	0023      	movs	r3, r4
 8800542:	f000 fbc5 	bl	8800cd0 <blend_glyph_4bpp>
 8800546:	9a18      	ldr	r2, [sp, #96]	@ 0x60
 8800548:	18a8      	adds	r0, r5, r2
 880054a:	aa1c      	add	r2, sp, #112	@ 0x70
 880054c:	0023      	movs	r3, r4
 880054e:	9201      	str	r2, [sp, #4]
 8800550:	2100      	movs	r1, #0
 8800552:	4642      	mov	r2, r8
 8800554:	9600      	str	r6, [sp, #0]
 8800556:	f000 fbbb 	bl	8800cd0 <blend_glyph_4bpp>
 880055a:	9b14      	ldr	r3, [sp, #80]	@ 0x50
 880055c:	2b00      	cmp	r3, #0
 880055e:	d000      	beq.n	8800562 <chs_emit.isra.0+0x306>
 8800560:	e166      	b.n	8800830 <chs_emit.isra.0+0x5d4>
 8800562:	9b10      	ldr	r3, [sp, #64]	@ 0x40
 8800564:	061d      	lsls	r5, r3, #24
 8800566:	4b24      	ldr	r3, [pc, #144]	@ (88005f8 <chs_emit.isra.0+0x39c>)
 8800568:	9c0e      	ldr	r4, [sp, #56]	@ 0x38
 880056a:	6819      	ldr	r1, [r3, #0]
 880056c:	7e63      	ldrb	r3, [r4, #25]
 880056e:	7e22      	ldrb	r2, [r4, #24]
 8800570:	0609      	lsls	r1, r1, #24
 8800572:	0e09      	lsrs	r1, r1, #24
 8800574:	021b      	lsls	r3, r3, #8
 8800576:	7da0      	ldrb	r0, [r4, #22]
 8800578:	4313      	orrs	r3, r2
 880057a:	7de2      	ldrb	r2, [r4, #23]
 880057c:	910a      	str	r1, [sp, #40]	@ 0x28
 880057e:	2107      	movs	r1, #7
 8800580:	0212      	lsls	r2, r2, #8
 8800582:	4302      	orrs	r2, r0
 8800584:	9817      	ldr	r0, [sp, #92]	@ 0x5c
 8800586:	4001      	ands	r1, r0
 8800588:	9109      	str	r1, [sp, #36]	@ 0x24
 880058a:	9915      	ldr	r1, [sp, #84]	@ 0x54
 880058c:	9f1a      	ldr	r7, [sp, #104]	@ 0x68
 880058e:	9106      	str	r1, [sp, #24]
 8800590:	9916      	ldr	r1, [sp, #88]	@ 0x58
 8800592:	0e2d      	lsrs	r5, r5, #24
 8800594:	9607      	str	r6, [sp, #28]
 8800596:	9508      	str	r5, [sp, #32]
 8800598:	9105      	str	r1, [sp, #20]
 880059a:	9704      	str	r7, [sp, #16]
 880059c:	7f61      	ldrb	r1, [r4, #29]
 880059e:	9103      	str	r1, [sp, #12]
 88005a0:	9913      	ldr	r1, [sp, #76]	@ 0x4c
 88005a2:	9102      	str	r1, [sp, #8]
 88005a4:	7f21      	ldrb	r1, [r4, #28]
 88005a6:	9101      	str	r1, [sp, #4]
 88005a8:	7ea1      	ldrb	r1, [r4, #26]
 88005aa:	0020      	movs	r0, r4
 88005ac:	9100      	str	r1, [sp, #0]
 88005ae:	4659      	mov	r1, fp
 88005b0:	f000 fde4 	bl	880117c <trace_glyph>
 88005b4:	9b1b      	ldr	r3, [sp, #108]	@ 0x6c
 88005b6:	041a      	lsls	r2, r3, #16
 88005b8:	0039      	movs	r1, r7
 88005ba:	0020      	movs	r0, r4
 88005bc:	0c12      	lsrs	r2, r2, #16
 88005be:	7ea6      	ldrb	r6, [r4, #26]
 88005c0:	f7ff fd2a 	bl	8800018 <UpdateTilemap_Origin>
 88005c4:	9b14      	ldr	r3, [sp, #80]	@ 0x50
 88005c6:	76a6      	strb	r6, [r4, #26]
 88005c8:	2b00      	cmp	r3, #0
 88005ca:	d000      	beq.n	88005ce <chs_emit.isra.0+0x372>
 88005cc:	e103      	b.n	88007d6 <chs_emit.isra.0+0x57a>
 88005ce:	9b13      	ldr	r3, [sp, #76]	@ 0x4c
 88005d0:	469c      	mov	ip, r3
 88005d2:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 88005d4:	4465      	add	r5, ip
 88005d6:	76dd      	strb	r5, [r3, #27]
 88005d8:	9b0f      	ldr	r3, [sp, #60]	@ 0x3c
 88005da:	0418      	lsls	r0, r3, #16
 88005dc:	0c00      	lsrs	r0, r0, #16
 88005de:	f000 fce1 	bl	8800fa4 <v8_phase_advance>
 88005e2:	4653      	mov	r3, sl
 88005e4:	2b01      	cmp	r3, #1
 88005e6:	d900      	bls.n	88005ea <chs_emit.isra.0+0x38e>
 88005e8:	e674      	b.n	88002d4 <chs_emit.isra.0+0x78>
 88005ea:	e67f      	b.n	88002ec <chs_emit.isra.0+0x90>
 88005ec:	0203ffd1 	.word	0x0203ffd1
 88005f0:	08003709 	.word	0x08003709
 88005f4:	00002c20 	.word	0x00002c20
 88005f8:	0203e8a8 	.word	0x0203e8a8
 88005fc:	2221      	movs	r2, #33	@ 0x21
 88005fe:	980e      	ldr	r0, [sp, #56]	@ 0x38
 8800600:	331e      	adds	r3, #30
 8800602:	5c82      	ldrb	r2, [r0, r2]
 8800604:	5cc3      	ldrb	r3, [r0, r3]
 8800606:	0212      	lsls	r2, r2, #8
 8800608:	431a      	orrs	r2, r3
 880060a:	2322      	movs	r3, #34	@ 0x22
 880060c:	5cc3      	ldrb	r3, [r0, r3]
 880060e:	041b      	lsls	r3, r3, #16
 8800610:	4313      	orrs	r3, r2
 8800612:	2223      	movs	r2, #35	@ 0x23
 8800614:	5c85      	ldrb	r5, [r0, r2]
 8800616:	062d      	lsls	r5, r5, #24
 8800618:	431d      	orrs	r5, r3
 880061a:	d100      	bne.n	880061e <chs_emit.isra.0+0x3c2>
 880061c:	e65a      	b.n	88002d4 <chs_emit.isra.0+0x78>
 880061e:	f000 fc9b 	bl	8800f58 <v8_phase_get>
 8800622:	2307      	movs	r3, #7
 8800624:	2708      	movs	r7, #8
 8800626:	4003      	ands	r3, r0
 8800628:	4699      	mov	r9, r3
 880062a:	1aff      	subs	r7, r7, r3
 880062c:	9b46      	ldr	r3, [sp, #280]	@ 0x118
 880062e:	429f      	cmp	r7, r3
 8800630:	d900      	bls.n	8800634 <chs_emit.isra.0+0x3d8>
 8800632:	001f      	movs	r7, r3
 8800634:	9b46      	ldr	r3, [sp, #280]	@ 0x118
 8800636:	9e0f      	ldr	r6, [sp, #60]	@ 0x3c
 8800638:	1bdb      	subs	r3, r3, r7
 880063a:	444e      	add	r6, r9
 880063c:	469b      	mov	fp, r3
 880063e:	08f3      	lsrs	r3, r6, #3
 8800640:	9310      	str	r3, [sp, #64]	@ 0x40
 8800642:	d101      	bne.n	8800648 <chs_emit.isra.0+0x3ec>
 8800644:	3301      	adds	r3, #1
 8800646:	9310      	str	r3, [sp, #64]	@ 0x40
 8800648:	4bd4      	ldr	r3, [pc, #848]	@ (880099c <chs_emit.isra.0+0x740>)
 880064a:	781a      	ldrb	r2, [r3, #0]
 880064c:	2a00      	cmp	r2, #0
 880064e:	d101      	bne.n	8800654 <chs_emit.isra.0+0x3f8>
 8800650:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 8800652:	7b1a      	ldrb	r2, [r3, #12]
 8800654:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 8800656:	7b58      	ldrb	r0, [r3, #13]
 8800658:	7b99      	ldrb	r1, [r3, #14]
 880065a:	0203      	lsls	r3, r0, #8
 880065c:	0406      	lsls	r6, r0, #16
 880065e:	4303      	orrs	r3, r0
 8800660:	4333      	orrs	r3, r6
 8800662:	2600      	movs	r6, #0
 8800664:	0600      	lsls	r0, r0, #24
 8800666:	4303      	orrs	r3, r0
 8800668:	9320      	str	r3, [sp, #128]	@ 0x80
 880066a:	9321      	str	r3, [sp, #132]	@ 0x84
 880066c:	9322      	str	r3, [sp, #136]	@ 0x88
 880066e:	9323      	str	r3, [sp, #140]	@ 0x8c
 8800670:	ab20      	add	r3, sp, #128	@ 0x80
 8800672:	930d      	str	r3, [sp, #52]	@ 0x34
 8800674:	7399      	strb	r1, [r3, #14]
 8800676:	73da      	strb	r2, [r3, #15]
 8800678:	ab34      	add	r3, sp, #208	@ 0xd0
 880067a:	9318      	str	r3, [sp, #96]	@ 0x60
 880067c:	c340      	stmia	r3!, {r6}
 880067e:	aa3c      	add	r2, sp, #240	@ 0xf0
 8800680:	4293      	cmp	r3, r2
 8800682:	d1fb      	bne.n	880067c <chs_emit.isra.0+0x420>
 8800684:	ab2c      	add	r3, sp, #176	@ 0xb0
 8800686:	469a      	mov	sl, r3
 8800688:	003a      	movs	r2, r7
 880068a:	2100      	movs	r1, #0
 880068c:	9300      	str	r3, [sp, #0]
 880068e:	9811      	ldr	r0, [sp, #68]	@ 0x44
 8800690:	ab24      	add	r3, sp, #144	@ 0x90
 8800692:	f000 fbd7 	bl	8800e44 <extract_cols>
 8800696:	464a      	mov	r2, r9
 8800698:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 880069a:	2100      	movs	r1, #0
 880069c:	9301      	str	r3, [sp, #4]
 880069e:	9200      	str	r2, [sp, #0]
 88006a0:	003b      	movs	r3, r7
 88006a2:	aa24      	add	r2, sp, #144	@ 0x90
 88006a4:	0028      	movs	r0, r5
 88006a6:	f000 fb13 	bl	8800cd0 <blend_glyph_4bpp>
 88006aa:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 88006ac:	002c      	movs	r4, r5
 88006ae:	9301      	str	r3, [sp, #4]
 88006b0:	464b      	mov	r3, r9
 88006b2:	3420      	adds	r4, #32
 88006b4:	9300      	str	r3, [sp, #0]
 88006b6:	4652      	mov	r2, sl
 88006b8:	003b      	movs	r3, r7
 88006ba:	2100      	movs	r1, #0
 88006bc:	0020      	movs	r0, r4
 88006be:	f000 fb07 	bl	8800cd0 <blend_glyph_4bpp>
 88006c2:	465b      	mov	r3, fp
 88006c4:	2b00      	cmp	r3, #0
 88006c6:	d000      	beq.n	88006ca <chs_emit.isra.0+0x46e>
 88006c8:	e128      	b.n	880091c <chs_emit.isra.0+0x6c0>
 88006ca:	444f      	add	r7, r9
 88006cc:	2f07      	cmp	r7, #7
 88006ce:	d942      	bls.n	8800756 <chs_emit.isra.0+0x4fa>
 88006d0:	9b10      	ldr	r3, [sp, #64]	@ 0x40
 88006d2:	019e      	lsls	r6, r3, #6
 88006d4:	2320      	movs	r3, #32
 88006d6:	990e      	ldr	r1, [sp, #56]	@ 0x38
 88006d8:	1976      	adds	r6, r6, r5
 88006da:	54ce      	strb	r6, [r1, r3]
 88006dc:	0a32      	lsrs	r2, r6, #8
 88006de:	3301      	adds	r3, #1
 88006e0:	54ca      	strb	r2, [r1, r3]
 88006e2:	0c32      	lsrs	r2, r6, #16
 88006e4:	3301      	adds	r3, #1
 88006e6:	54ca      	strb	r2, [r1, r3]
 88006e8:	0e36      	lsrs	r6, r6, #24
 88006ea:	3301      	adds	r3, #1
 88006ec:	54ce      	strb	r6, [r1, r3]
 88006ee:	9b0f      	ldr	r3, [sp, #60]	@ 0x3c
 88006f0:	0418      	lsls	r0, r3, #16
 88006f2:	0c00      	lsrs	r0, r0, #16
 88006f4:	f000 fc56 	bl	8800fa4 <v8_phase_advance>
 88006f8:	e5ec      	b.n	88002d4 <chs_emit.isra.0+0x78>
 88006fa:	2300      	movs	r3, #0
 88006fc:	27b0      	movs	r7, #176	@ 0xb0
 88006fe:	4698      	mov	r8, r3
 8800700:	2428      	movs	r4, #40	@ 0x28
 8800702:	007f      	lsls	r7, r7, #1
 8800704:	e632      	b.n	880036c <chs_emit.isra.0+0x110>
 8800706:	4649      	mov	r1, r9
 8800708:	2000      	movs	r0, #0
 880070a:	f7ff fcc3 	bl	8800094 <chs_slot_for>
 880070e:	2827      	cmp	r0, #39	@ 0x27
 8800710:	d900      	bls.n	8800714 <chs_emit.isra.0+0x4b8>
 8800712:	e5dc      	b.n	88002ce <chs_emit.isra.0+0x72>
 8800714:	3058      	adds	r0, #88	@ 0x58
 8800716:	0480      	lsls	r0, r0, #18
 8800718:	0c03      	lsrs	r3, r0, #16
 880071a:	931a      	str	r3, [sp, #104]	@ 0x68
 880071c:	e67a      	b.n	8800414 <chs_emit.isra.0+0x1b8>
 880071e:	00a3      	lsls	r3, r4, #2
 8800720:	19db      	adds	r3, r3, r7
 8800722:	429a      	cmp	r2, r3
 8800724:	d300      	bcc.n	8800728 <chs_emit.isra.0+0x4cc>
 8800726:	e636      	b.n	8800396 <chs_emit.isra.0+0x13a>
 8800728:	2303      	movs	r3, #3
 880072a:	0011      	movs	r1, r2
 880072c:	1bd2      	subs	r2, r2, r7
 880072e:	4013      	ands	r3, r2
 8800730:	2b02      	cmp	r3, #2
 8800732:	d000      	beq.n	8800736 <chs_emit.isra.0+0x4da>
 8800734:	e62f      	b.n	8800396 <chs_emit.isra.0+0x13a>
 8800736:	2900      	cmp	r1, #0
 8800738:	d100      	bne.n	880073c <chs_emit.isra.0+0x4e0>
 880073a:	e12c      	b.n	8800996 <chs_emit.isra.0+0x73a>
 880073c:	4643      	mov	r3, r8
 880073e:	4998      	ldr	r1, [pc, #608]	@ (88009a0 <chs_emit.isra.0+0x744>)
 8800740:	0392      	lsls	r2, r2, #14
 8800742:	3b01      	subs	r3, #1
 8800744:	0c12      	lsrs	r2, r2, #16
 8800746:	00d2      	lsls	r2, r2, #3
 8800748:	400b      	ands	r3, r1
 880074a:	189b      	adds	r3, r3, r2
 880074c:	4a95      	ldr	r2, [pc, #596]	@ (88009a4 <chs_emit.isra.0+0x748>)
 880074e:	4694      	mov	ip, r2
 8800750:	4463      	add	r3, ip
 8800752:	681a      	ldr	r2, [r3, #0]
 8800754:	e622      	b.n	880039c <chs_emit.isra.0+0x140>
 8800756:	2308      	movs	r3, #8
 8800758:	9a18      	ldr	r2, [sp, #96]	@ 0x60
 880075a:	1bdb      	subs	r3, r3, r7
 880075c:	4698      	mov	r8, r3
 880075e:	4691      	mov	r9, r2
 8800760:	9e0d      	ldr	r6, [sp, #52]	@ 0x34
 8800762:	2100      	movs	r1, #0
 8800764:	0028      	movs	r0, r5
 8800766:	9601      	str	r6, [sp, #4]
 8800768:	9700      	str	r7, [sp, #0]
 880076a:	f000 fab1 	bl	8800cd0 <blend_glyph_4bpp>
 880076e:	4643      	mov	r3, r8
 8800770:	464a      	mov	r2, r9
 8800772:	2100      	movs	r1, #0
 8800774:	0020      	movs	r0, r4
 8800776:	9601      	str	r6, [sp, #4]
 8800778:	9700      	str	r7, [sp, #0]
 880077a:	f000 faa9 	bl	8800cd0 <blend_glyph_4bpp>
 880077e:	e7a7      	b.n	88006d0 <chs_emit.isra.0+0x474>
 8800780:	9b1a      	ldr	r3, [sp, #104]	@ 0x68
 8800782:	015a      	lsls	r2, r3, #5
 8800784:	3301      	adds	r3, #1
 8800786:	931b      	str	r3, [sp, #108]	@ 0x6c
 8800788:	015b      	lsls	r3, r3, #5
 880078a:	9219      	str	r2, [sp, #100]	@ 0x64
 880078c:	9318      	str	r3, [sp, #96]	@ 0x60
 880078e:	2e00      	cmp	r6, #0
 8800790:	d000      	beq.n	8800794 <chs_emit.isra.0+0x538>
 8800792:	e0fd      	b.n	8800990 <chs_emit.isra.0+0x734>
 8800794:	ab2c      	add	r3, sp, #176	@ 0xb0
 8800796:	4698      	mov	r8, r3
 8800798:	9c12      	ldr	r4, [sp, #72]	@ 0x48
 880079a:	2100      	movs	r1, #0
 880079c:	0022      	movs	r2, r4
 880079e:	9300      	str	r3, [sp, #0]
 88007a0:	9811      	ldr	r0, [sp, #68]	@ 0x44
 88007a2:	ab24      	add	r3, sp, #144	@ 0x90
 88007a4:	f000 fb4e 	bl	8800e44 <extract_cols>
 88007a8:	9b19      	ldr	r3, [sp, #100]	@ 0x64
 88007aa:	18e8      	adds	r0, r5, r3
 88007ac:	ab1c      	add	r3, sp, #112	@ 0x70
 88007ae:	2100      	movs	r1, #0
 88007b0:	9301      	str	r3, [sp, #4]
 88007b2:	aa24      	add	r2, sp, #144	@ 0x90
 88007b4:	0023      	movs	r3, r4
 88007b6:	9600      	str	r6, [sp, #0]
 88007b8:	f000 fa8a 	bl	8800cd0 <blend_glyph_4bpp>
 88007bc:	9a18      	ldr	r2, [sp, #96]	@ 0x60
 88007be:	18a8      	adds	r0, r5, r2
 88007c0:	aa1c      	add	r2, sp, #112	@ 0x70
 88007c2:	0023      	movs	r3, r4
 88007c4:	9201      	str	r2, [sp, #4]
 88007c6:	2100      	movs	r1, #0
 88007c8:	4642      	mov	r2, r8
 88007ca:	9600      	str	r6, [sp, #0]
 88007cc:	f000 fa80 	bl	8800cd0 <blend_glyph_4bpp>
 88007d0:	2300      	movs	r3, #0
 88007d2:	9316      	str	r3, [sp, #88]	@ 0x58
 88007d4:	e6c5      	b.n	8800562 <chs_emit.isra.0+0x306>
 88007d6:	9916      	ldr	r1, [sp, #88]	@ 0x58
 88007d8:	9b13      	ldr	r3, [sp, #76]	@ 0x4c
 88007da:	9c0e      	ldr	r4, [sp, #56]	@ 0x38
 88007dc:	1c4a      	adds	r2, r1, #1
 88007de:	3301      	adds	r3, #1
 88007e0:	0412      	lsls	r2, r2, #16
 88007e2:	0020      	movs	r0, r4
 88007e4:	76e3      	strb	r3, [r4, #27]
 88007e6:	0c12      	lsrs	r2, r2, #16
 88007e8:	f7ff fc16 	bl	8800018 <UpdateTilemap_Origin>
 88007ec:	76a6      	strb	r6, [r4, #26]
 88007ee:	e6ee      	b.n	88005ce <chs_emit.isra.0+0x372>
 88007f0:	ab24      	add	r3, sp, #144	@ 0x90
 88007f2:	4699      	mov	r9, r3
 88007f4:	ab2c      	add	r3, sp, #176	@ 0xb0
 88007f6:	4698      	mov	r8, r3
 88007f8:	9c12      	ldr	r4, [sp, #72]	@ 0x48
 88007fa:	2100      	movs	r1, #0
 88007fc:	0022      	movs	r2, r4
 88007fe:	9300      	str	r3, [sp, #0]
 8800800:	9811      	ldr	r0, [sp, #68]	@ 0x44
 8800802:	464b      	mov	r3, r9
 8800804:	f000 fb1e 	bl	8800e44 <extract_cols>
 8800808:	9b19      	ldr	r3, [sp, #100]	@ 0x64
 880080a:	18e8      	adds	r0, r5, r3
 880080c:	ab1c      	add	r3, sp, #112	@ 0x70
 880080e:	464a      	mov	r2, r9
 8800810:	2100      	movs	r1, #0
 8800812:	9301      	str	r3, [sp, #4]
 8800814:	9600      	str	r6, [sp, #0]
 8800816:	0023      	movs	r3, r4
 8800818:	f000 fa5a 	bl	8800cd0 <blend_glyph_4bpp>
 880081c:	9a18      	ldr	r2, [sp, #96]	@ 0x60
 880081e:	18a8      	adds	r0, r5, r2
 8800820:	aa1c      	add	r2, sp, #112	@ 0x70
 8800822:	9201      	str	r2, [sp, #4]
 8800824:	0023      	movs	r3, r4
 8800826:	4642      	mov	r2, r8
 8800828:	2100      	movs	r1, #0
 880082a:	9600      	str	r6, [sp, #0]
 880082c:	f000 fa50 	bl	8800cd0 <blend_glyph_4bpp>
 8800830:	4643      	mov	r3, r8
 8800832:	2700      	movs	r7, #0
 8800834:	9300      	str	r3, [sp, #0]
 8800836:	9a14      	ldr	r2, [sp, #80]	@ 0x50
 8800838:	464b      	mov	r3, r9
 880083a:	9912      	ldr	r1, [sp, #72]	@ 0x48
 880083c:	9811      	ldr	r0, [sp, #68]	@ 0x44
 880083e:	f000 fb01 	bl	8800e44 <extract_cols>
 8800842:	9b16      	ldr	r3, [sp, #88]	@ 0x58
 8800844:	a91c      	add	r1, sp, #112	@ 0x70
 8800846:	015c      	lsls	r4, r3, #5
 8800848:	464a      	mov	r2, r9
 880084a:	9101      	str	r1, [sp, #4]
 880084c:	9b14      	ldr	r3, [sp, #80]	@ 0x50
 880084e:	2100      	movs	r1, #0
 8800850:	1928      	adds	r0, r5, r4
 8800852:	9700      	str	r7, [sp, #0]
 8800854:	f000 fa3c 	bl	8800cd0 <blend_glyph_4bpp>
 8800858:	9a16      	ldr	r2, [sp, #88]	@ 0x58
 880085a:	1c53      	adds	r3, r2, #1
 880085c:	015a      	lsls	r2, r3, #5
 880085e:	4691      	mov	r9, r2
 8800860:	0028      	movs	r0, r5
 8800862:	9d14      	ldr	r5, [sp, #80]	@ 0x50
 8800864:	aa1c      	add	r2, sp, #112	@ 0x70
 8800866:	002b      	movs	r3, r5
 8800868:	9201      	str	r2, [sp, #4]
 880086a:	2100      	movs	r1, #0
 880086c:	4642      	mov	r2, r8
 880086e:	9700      	str	r7, [sp, #0]
 8800870:	4448      	add	r0, r9
 8800872:	f000 fa2d 	bl	8800cd0 <blend_glyph_4bpp>
 8800876:	980e      	ldr	r0, [sp, #56]	@ 0x38
 8800878:	7843      	ldrb	r3, [r0, #1]
 880087a:	7802      	ldrb	r2, [r0, #0]
 880087c:	021b      	lsls	r3, r3, #8
 880087e:	4313      	orrs	r3, r2
 8800880:	7882      	ldrb	r2, [r0, #2]
 8800882:	0412      	lsls	r2, r2, #16
 8800884:	431a      	orrs	r2, r3
 8800886:	78c3      	ldrb	r3, [r0, #3]
 8800888:	061b      	lsls	r3, r3, #24
 880088a:	4313      	orrs	r3, r2
 880088c:	d100      	bne.n	8800890 <chs_emit.isra.0+0x634>
 880088e:	e668      	b.n	8800562 <chs_emit.isra.0+0x306>
 8800890:	2d07      	cmp	r5, #7
 8800892:	d900      	bls.n	8800896 <chs_emit.isra.0+0x63a>
 8800894:	e665      	b.n	8800562 <chs_emit.isra.0+0x306>
 8800896:	7b59      	ldrb	r1, [r3, #13]
 8800898:	7b1a      	ldrb	r2, [r3, #12]
 880089a:	0209      	lsls	r1, r1, #8
 880089c:	4311      	orrs	r1, r2
 880089e:	7b9a      	ldrb	r2, [r3, #14]
 88008a0:	7bdd      	ldrb	r5, [r3, #15]
 88008a2:	0412      	lsls	r2, r2, #16
 88008a4:	430a      	orrs	r2, r1
 88008a6:	062d      	lsls	r5, r5, #24
 88008a8:	4315      	orrs	r5, r2
 88008aa:	d100      	bne.n	88008ae <chs_emit.isra.0+0x652>
 88008ac:	e659      	b.n	8800562 <chs_emit.isra.0+0x306>
 88008ae:	4b3b      	ldr	r3, [pc, #236]	@ (880099c <chs_emit.isra.0+0x740>)
 88008b0:	781a      	ldrb	r2, [r3, #0]
 88008b2:	2a00      	cmp	r2, #0
 88008b4:	d100      	bne.n	88008b8 <chs_emit.isra.0+0x65c>
 88008b6:	7b02      	ldrb	r2, [r0, #12]
 88008b8:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 88008ba:	7b58      	ldrb	r0, [r3, #13]
 88008bc:	7b99      	ldrb	r1, [r3, #14]
 88008be:	0203      	lsls	r3, r0, #8
 88008c0:	0407      	lsls	r7, r0, #16
 88008c2:	4303      	orrs	r3, r0
 88008c4:	433b      	orrs	r3, r7
 88008c6:	0600      	lsls	r0, r0, #24
 88008c8:	4303      	orrs	r3, r0
 88008ca:	9320      	str	r3, [sp, #128]	@ 0x80
 88008cc:	9321      	str	r3, [sp, #132]	@ 0x84
 88008ce:	9322      	str	r3, [sp, #136]	@ 0x88
 88008d0:	9323      	str	r3, [sp, #140]	@ 0x8c
 88008d2:	ab20      	add	r3, sp, #128	@ 0x80
 88008d4:	73da      	strb	r2, [r3, #15]
 88008d6:	2200      	movs	r2, #0
 88008d8:	930d      	str	r3, [sp, #52]	@ 0x34
 88008da:	7399      	strb	r1, [r3, #14]
 88008dc:	ab34      	add	r3, sp, #208	@ 0xd0
 88008de:	9318      	str	r3, [sp, #96]	@ 0x60
 88008e0:	c304      	stmia	r3!, {r2}
 88008e2:	a93c      	add	r1, sp, #240	@ 0xf0
 88008e4:	4299      	cmp	r1, r3
 88008e6:	d1fb      	bne.n	88008e0 <chs_emit.isra.0+0x684>
 88008e8:	9b12      	ldr	r3, [sp, #72]	@ 0x48
 88008ea:	9a46      	ldr	r2, [sp, #280]	@ 0x118
 88008ec:	1928      	adds	r0, r5, r4
 88008ee:	1a9f      	subs	r7, r3, r2
 88008f0:	9c0d      	ldr	r4, [sp, #52]	@ 0x34
 88008f2:	9b14      	ldr	r3, [sp, #80]	@ 0x50
 88008f4:	9a18      	ldr	r2, [sp, #96]	@ 0x60
 88008f6:	3708      	adds	r7, #8
 88008f8:	9300      	str	r3, [sp, #0]
 88008fa:	2100      	movs	r1, #0
 88008fc:	003b      	movs	r3, r7
 88008fe:	9401      	str	r4, [sp, #4]
 8800900:	4690      	mov	r8, r2
 8800902:	f000 f9e5 	bl	8800cd0 <blend_glyph_4bpp>
 8800906:	0028      	movs	r0, r5
 8800908:	9b14      	ldr	r3, [sp, #80]	@ 0x50
 880090a:	4642      	mov	r2, r8
 880090c:	9300      	str	r3, [sp, #0]
 880090e:	2100      	movs	r1, #0
 8800910:	003b      	movs	r3, r7
 8800912:	9401      	str	r4, [sp, #4]
 8800914:	4448      	add	r0, r9
 8800916:	f000 f9db 	bl	8800cd0 <blend_glyph_4bpp>
 880091a:	e622      	b.n	8800562 <chs_emit.isra.0+0x306>
 880091c:	4653      	mov	r3, sl
 880091e:	465a      	mov	r2, fp
 8800920:	0039      	movs	r1, r7
 8800922:	9300      	str	r3, [sp, #0]
 8800924:	9811      	ldr	r0, [sp, #68]	@ 0x44
 8800926:	ab24      	add	r3, sp, #144	@ 0x90
 8800928:	f000 fa8c 	bl	8800e44 <extract_cols>
 880092c:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 880092e:	3420      	adds	r4, #32
 8800930:	2100      	movs	r1, #0
 8800932:	9301      	str	r3, [sp, #4]
 8800934:	aa24      	add	r2, sp, #144	@ 0x90
 8800936:	465b      	mov	r3, fp
 8800938:	0020      	movs	r0, r4
 880093a:	9600      	str	r6, [sp, #0]
 880093c:	f000 f9c8 	bl	8800cd0 <blend_glyph_4bpp>
 8800940:	2260      	movs	r2, #96	@ 0x60
 8800942:	4691      	mov	r9, r2
 8800944:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 8800946:	44a9      	add	r9, r5
 8800948:	9301      	str	r3, [sp, #4]
 880094a:	4652      	mov	r2, sl
 880094c:	465b      	mov	r3, fp
 880094e:	2100      	movs	r1, #0
 8800950:	4648      	mov	r0, r9
 8800952:	9600      	str	r6, [sp, #0]
 8800954:	f000 f9bc 	bl	8800cd0 <blend_glyph_4bpp>
 8800958:	465b      	mov	r3, fp
 880095a:	2b07      	cmp	r3, #7
 880095c:	d900      	bls.n	8800960 <chs_emit.isra.0+0x704>
 880095e:	e6b7      	b.n	88006d0 <chs_emit.isra.0+0x474>
 8800960:	9b46      	ldr	r3, [sp, #280]	@ 0x118
 8800962:	1aff      	subs	r7, r7, r3
 8800964:	465b      	mov	r3, fp
 8800966:	9e0d      	ldr	r6, [sp, #52]	@ 0x34
 8800968:	9a18      	ldr	r2, [sp, #96]	@ 0x60
 880096a:	3708      	adds	r7, #8
 880096c:	9300      	str	r3, [sp, #0]
 880096e:	2100      	movs	r1, #0
 8800970:	003b      	movs	r3, r7
 8800972:	0020      	movs	r0, r4
 8800974:	9601      	str	r6, [sp, #4]
 8800976:	4690      	mov	r8, r2
 8800978:	f000 f9aa 	bl	8800cd0 <blend_glyph_4bpp>
 880097c:	465b      	mov	r3, fp
 880097e:	4642      	mov	r2, r8
 8800980:	9300      	str	r3, [sp, #0]
 8800982:	2100      	movs	r1, #0
 8800984:	003b      	movs	r3, r7
 8800986:	4648      	mov	r0, r9
 8800988:	9601      	str	r6, [sp, #4]
 880098a:	f000 f9a1 	bl	8800cd0 <blend_glyph_4bpp>
 880098e:	e69f      	b.n	88006d0 <chs_emit.isra.0+0x474>
 8800990:	2300      	movs	r3, #0
 8800992:	9316      	str	r3, [sp, #88]	@ 0x58
 8800994:	e55b      	b.n	880044e <chs_emit.isra.0+0x1f2>
 8800996:	2200      	movs	r2, #0
 8800998:	e500      	b.n	880039c <chs_emit.isra.0+0x140>
 880099a:	46c0      	nop			@ (mov r8, r8)
 880099c:	0203ffd1 	.word	0x0203ffd1
 88009a0:	fffffbb0 	.word	0xfffffbb0
 88009a4:	0203e458 	.word	0x0203e458

088009a8 <DrawGlyph.part.0>:
 88009a8:	b5f0      	push	{r4, r5, r6, r7, lr}
 88009aa:	46d6      	mov	lr, sl
 88009ac:	4646      	mov	r6, r8
 88009ae:	464f      	mov	r7, r9
 88009b0:	2313      	movs	r3, #19
 88009b2:	b5c0      	push	{r6, r7, lr}
 88009b4:	b0a8      	sub	sp, #160	@ 0xa0
 88009b6:	446b      	add	r3, sp
 88009b8:	4698      	mov	r8, r3
 88009ba:	2316      	movs	r3, #22
 88009bc:	446b      	add	r3, sp
 88009be:	9301      	str	r3, [sp, #4]
 88009c0:	2717      	movs	r7, #23
 88009c2:	2315      	movs	r3, #21
 88009c4:	000e      	movs	r6, r1
 88009c6:	ad05      	add	r5, sp, #20
 88009c8:	446b      	add	r3, sp
 88009ca:	446f      	add	r7, sp
 88009cc:	4642      	mov	r2, r8
 88009ce:	2100      	movs	r1, #0
 88009d0:	9300      	str	r3, [sp, #0]
 88009d2:	9702      	str	r7, [sp, #8]
 88009d4:	002b      	movs	r3, r5
 88009d6:	4682      	mov	sl, r0
 88009d8:	f7ff fc02 	bl	88001e0 <resolve_draw>
 88009dc:	4b2e      	ldr	r3, [pc, #184]	@ (8800a98 <DrawGlyph.part.0+0xf0>)
 88009de:	601e      	str	r6, [r3, #0]
 88009e0:	782d      	ldrb	r5, [r5, #0]
 88009e2:	ab07      	add	r3, sp, #28
 88009e4:	aa06      	add	r2, sp, #24
 88009e6:	0031      	movs	r1, r6
 88009e8:	0028      	movs	r0, r5
 88009ea:	4c2c      	ldr	r4, [pc, #176]	@ (8800a9c <DrawGlyph.part.0+0xf4>)
 88009ec:	f000 f96d 	bl	8800cca <PrintNextChar_Hook+0xb6>
 88009f0:	2200      	movs	r2, #0
 88009f2:	ab08      	add	r3, sp, #32
 88009f4:	c304      	stmia	r3!, {r2}
 88009f6:	a928      	add	r1, sp, #160	@ 0xa0
 88009f8:	4299      	cmp	r1, r3
 88009fa:	d1fb      	bne.n	88009f4 <DrawGlyph.part.0+0x4c>
 88009fc:	3d03      	subs	r5, #3
 88009fe:	062b      	lsls	r3, r5, #24
 8800a00:	9806      	ldr	r0, [sp, #24]
 8800a02:	0e1b      	lsrs	r3, r3, #24
 8800a04:	2b02      	cmp	r3, #2
 8800a06:	d839      	bhi.n	8800a7c <DrawGlyph.part.0+0xd4>
 8800a08:	6803      	ldr	r3, [r0, #0]
 8800a0a:	9308      	str	r3, [sp, #32]
 8800a0c:	6843      	ldr	r3, [r0, #4]
 8800a0e:	9309      	str	r3, [sp, #36]	@ 0x24
 8800a10:	6883      	ldr	r3, [r0, #8]
 8800a12:	930a      	str	r3, [sp, #40]	@ 0x28
 8800a14:	68c3      	ldr	r3, [r0, #12]
 8800a16:	930b      	str	r3, [sp, #44]	@ 0x2c
 8800a18:	6903      	ldr	r3, [r0, #16]
 8800a1a:	930c      	str	r3, [sp, #48]	@ 0x30
 8800a1c:	6943      	ldr	r3, [r0, #20]
 8800a1e:	930d      	str	r3, [sp, #52]	@ 0x34
 8800a20:	6983      	ldr	r3, [r0, #24]
 8800a22:	930e      	str	r3, [sp, #56]	@ 0x38
 8800a24:	69c3      	ldr	r3, [r0, #28]
 8800a26:	930f      	str	r3, [sp, #60]	@ 0x3c
 8800a28:	9b07      	ldr	r3, [sp, #28]
 8800a2a:	681a      	ldr	r2, [r3, #0]
 8800a2c:	9210      	str	r2, [sp, #64]	@ 0x40
 8800a2e:	685a      	ldr	r2, [r3, #4]
 8800a30:	9211      	str	r2, [sp, #68]	@ 0x44
 8800a32:	689a      	ldr	r2, [r3, #8]
 8800a34:	9212      	str	r2, [sp, #72]	@ 0x48
 8800a36:	68da      	ldr	r2, [r3, #12]
 8800a38:	9213      	str	r2, [sp, #76]	@ 0x4c
 8800a3a:	691a      	ldr	r2, [r3, #16]
 8800a3c:	9214      	str	r2, [sp, #80]	@ 0x50
 8800a3e:	695a      	ldr	r2, [r3, #20]
 8800a40:	9215      	str	r2, [sp, #84]	@ 0x54
 8800a42:	699a      	ldr	r2, [r3, #24]
 8800a44:	9216      	str	r2, [sp, #88]	@ 0x58
 8800a46:	69db      	ldr	r3, [r3, #28]
 8800a48:	9317      	str	r3, [sp, #92]	@ 0x5c
 8800a4a:	4643      	mov	r3, r8
 8800a4c:	22fc      	movs	r2, #252	@ 0xfc
 8800a4e:	7819      	ldrb	r1, [r3, #0]
 8800a50:	783b      	ldrb	r3, [r7, #0]
 8800a52:	0092      	lsls	r2, r2, #2
 8800a54:	011b      	lsls	r3, r3, #4
 8800a56:	4013      	ands	r3, r2
 8800a58:	2208      	movs	r2, #8
 8800a5a:	0236      	lsls	r6, r6, #8
 8800a5c:	4333      	orrs	r3, r6
 8800a5e:	4313      	orrs	r3, r2
 8800a60:	9301      	str	r3, [sp, #4]
 8800a62:	4650      	mov	r0, sl
 8800a64:	9200      	str	r2, [sp, #0]
 8800a66:	ab08      	add	r3, sp, #32
 8800a68:	f7ff fbf8 	bl	880025c <chs_emit.isra.0>
 8800a6c:	b028      	add	sp, #160	@ 0xa0
 8800a6e:	bce0      	pop	{r5, r6, r7}
 8800a70:	46ba      	mov	sl, r7
 8800a72:	46b1      	mov	r9, r6
 8800a74:	46a8      	mov	r8, r5
 8800a76:	bcf0      	pop	{r4, r5, r6, r7}
 8800a78:	bc01      	pop	{r0}
 8800a7a:	4700      	bx	r0
 8800a7c:	a908      	add	r1, sp, #32
 8800a7e:	2300      	movs	r3, #0
 8800a80:	220f      	movs	r2, #15
 8800a82:	4d07      	ldr	r5, [pc, #28]	@ (8800aa0 <DrawGlyph.part.0+0xf8>)
 8800a84:	f000 f922 	bl	8800ccc <PrintNextChar_Hook+0xb8>
 8800a88:	2300      	movs	r3, #0
 8800a8a:	220f      	movs	r2, #15
 8800a8c:	9807      	ldr	r0, [sp, #28]
 8800a8e:	a910      	add	r1, sp, #64	@ 0x40
 8800a90:	f000 f91c 	bl	8800ccc <PrintNextChar_Hook+0xb8>
 8800a94:	e7d9      	b.n	8800a4a <DrawGlyph.part.0+0xa2>
 8800a96:	46c0      	nop			@ (mov r8, r8)
 8800a98:	0203e8a8 	.word	0x0203e8a8
 8800a9c:	08003731 	.word	0x08003731
 8800aa0:	08003831 	.word	0x08003831

08800aa4 <chs_print>:
 8800aa4:	b5f0      	push	{r4, r5, r6, r7, lr}
 8800aa6:	46d6      	mov	lr, sl
 8800aa8:	464f      	mov	r7, r9
 8800aaa:	4646      	mov	r6, r8
 8800aac:	b5c0      	push	{r6, r7, lr}
 8800aae:	b0a6      	sub	sp, #152	@ 0x98
 8800ab0:	000d      	movs	r5, r1
 8800ab2:	2300      	movs	r3, #0
 8800ab4:	0011      	movs	r1, r2
 8800ab6:	466a      	mov	r2, sp
 8800ab8:	75d3      	strb	r3, [r2, #23]
 8800aba:	3313      	adds	r3, #19
 8800abc:	446b      	add	r3, sp
 8800abe:	4699      	mov	r9, r3
 8800ac0:	2616      	movs	r6, #22
 8800ac2:	2315      	movs	r3, #21
 8800ac4:	2212      	movs	r2, #18
 8800ac6:	446b      	add	r3, sp
 8800ac8:	446e      	add	r6, sp
 8800aca:	af05      	add	r7, sp, #20
 8800acc:	9602      	str	r6, [sp, #8]
 8800ace:	9301      	str	r3, [sp, #4]
 8800ad0:	446a      	add	r2, sp
 8800ad2:	4698      	mov	r8, r3
 8800ad4:	9700      	str	r7, [sp, #0]
 8800ad6:	464b      	mov	r3, r9
 8800ad8:	0004      	movs	r4, r0
 8800ada:	f7ff fb81 	bl	88001e0 <resolve_draw>
 8800ade:	23ff      	movs	r3, #255	@ 0xff
 8800ae0:	4a18      	ldr	r2, [pc, #96]	@ (8800b44 <chs_print+0xa0>)
 8800ae2:	402b      	ands	r3, r5
 8800ae4:	6013      	str	r3, [r2, #0]
 8800ae6:	7ae3      	ldrb	r3, [r4, #11]
 8800ae8:	469a      	mov	sl, r3
 8800aea:	464b      	mov	r3, r9
 8800aec:	781b      	ldrb	r3, [r3, #0]
 8800aee:	72e3      	strb	r3, [r4, #11]
 8800af0:	2317      	movs	r3, #23
 8800af2:	7836      	ldrb	r6, [r6, #0]
 8800af4:	446b      	add	r3, sp
 8800af6:	0029      	movs	r1, r5
 8800af8:	0020      	movs	r0, r4
 8800afa:	9600      	str	r6, [sp, #0]
 8800afc:	aa06      	add	r2, sp, #24
 8800afe:	f000 fed9 	bl	88018b4 <GetGlyph>
 8800b02:	4653      	mov	r3, sl
 8800b04:	72e3      	strb	r3, [r4, #11]
 8800b06:	2800      	cmp	r0, #0
 8800b08:	d013      	beq.n	8800b32 <chs_print+0x8e>
 8800b0a:	4643      	mov	r3, r8
 8800b0c:	7818      	ldrb	r0, [r3, #0]
 8800b0e:	466b      	mov	r3, sp
 8800b10:	7c99      	ldrb	r1, [r3, #18]
 8800b12:	23fc      	movs	r3, #252	@ 0xfc
 8800b14:	0136      	lsls	r6, r6, #4
 8800b16:	009b      	lsls	r3, r3, #2
 8800b18:	401e      	ands	r6, r3
 8800b1a:	230f      	movs	r3, #15
 8800b1c:	022d      	lsls	r5, r5, #8
 8800b1e:	4003      	ands	r3, r0
 8800b20:	432e      	orrs	r6, r5
 8800b22:	431e      	orrs	r6, r3
 8800b24:	783a      	ldrb	r2, [r7, #0]
 8800b26:	ab06      	add	r3, sp, #24
 8800b28:	9000      	str	r0, [sp, #0]
 8800b2a:	9601      	str	r6, [sp, #4]
 8800b2c:	0020      	movs	r0, r4
 8800b2e:	f7ff fb95 	bl	880025c <chs_emit.isra.0>
 8800b32:	b026      	add	sp, #152	@ 0x98
 8800b34:	bce0      	pop	{r5, r6, r7}
 8800b36:	46ba      	mov	sl, r7
 8800b38:	46b1      	mov	r9, r6
 8800b3a:	46a8      	mov	r8, r5
 8800b3c:	bcf0      	pop	{r4, r5, r6, r7}
 8800b3e:	bc01      	pop	{r0}
 8800b40:	4700      	bx	r0
 8800b42:	46c0      	nop			@ (mov r8, r8)
 8800b44:	0203e8a8 	.word	0x0203e8a8

08800b48 <DrawHalfWidth>:
 8800b48:	b5f0      	push	{r4, r5, r6, r7, lr}
 8800b4a:	46d6      	mov	lr, sl
 8800b4c:	4646      	mov	r6, r8
 8800b4e:	464f      	mov	r7, r9
 8800b50:	000c      	movs	r4, r1
 8800b52:	b5c0      	push	{r6, r7, lr}
 8800b54:	3c36      	subs	r4, #54	@ 0x36
 8800b56:	4680      	mov	r8, r0
 8800b58:	468a      	mov	sl, r1
 8800b5a:	2000      	movs	r0, #0
 8800b5c:	b0a6      	sub	sp, #152	@ 0x98
 8800b5e:	2c08      	cmp	r4, #8
 8800b60:	d907      	bls.n	8800b72 <DrawHalfWidth+0x2a>
 8800b62:	b026      	add	sp, #152	@ 0x98
 8800b64:	bce0      	pop	{r5, r6, r7}
 8800b66:	46ba      	mov	sl, r7
 8800b68:	46b1      	mov	r9, r6
 8800b6a:	46a8      	mov	r8, r5
 8800b6c:	bcf0      	pop	{r4, r5, r6, r7}
 8800b6e:	bc02      	pop	{r1}
 8800b70:	4708      	bx	r1
 8800b72:	2313      	movs	r3, #19
 8800b74:	446b      	add	r3, sp
 8800b76:	4699      	mov	r9, r3
 8800b78:	2316      	movs	r3, #22
 8800b7a:	446b      	add	r3, sp
 8800b7c:	9301      	str	r3, [sp, #4]
 8800b7e:	2617      	movs	r6, #23
 8800b80:	2315      	movs	r3, #21
 8800b82:	446e      	add	r6, sp
 8800b84:	446b      	add	r3, sp
 8800b86:	464a      	mov	r2, r9
 8800b88:	2100      	movs	r1, #0
 8800b8a:	4640      	mov	r0, r8
 8800b8c:	9300      	str	r3, [sp, #0]
 8800b8e:	9602      	str	r6, [sp, #8]
 8800b90:	ab05      	add	r3, sp, #20
 8800b92:	f7ff fb25 	bl	88001e0 <resolve_draw>
 8800b96:	4b15      	ldr	r3, [pc, #84]	@ (8800bec <DrawHalfWidth+0xa4>)
 8800b98:	469c      	mov	ip, r3
 8800b9a:	ab06      	add	r3, sp, #24
 8800b9c:	001a      	movs	r2, r3
 8800b9e:	2100      	movs	r1, #0
 8800ba0:	01a0      	lsls	r0, r4, #6
 8800ba2:	4460      	add	r0, ip
 8800ba4:	c202      	stmia	r2!, {r1}
 8800ba6:	ac26      	add	r4, sp, #152	@ 0x98
 8800ba8:	42a2      	cmp	r2, r4
 8800baa:	d1fb      	bne.n	8800ba4 <DrawHalfWidth+0x5c>
 8800bac:	2201      	movs	r2, #1
 8800bae:	1e47      	subs	r7, r0, #1
 8800bb0:	301f      	adds	r0, #31
 8800bb2:	5cb9      	ldrb	r1, [r7, r2]
 8800bb4:	5c85      	ldrb	r5, [r0, r2]
 8800bb6:	54b1      	strb	r1, [r6, r2]
 8800bb8:	189c      	adds	r4, r3, r2
 8800bba:	3201      	adds	r2, #1
 8800bbc:	77e5      	strb	r5, [r4, #31]
 8800bbe:	2a21      	cmp	r2, #33	@ 0x21
 8800bc0:	d1f7      	bne.n	8800bb2 <DrawHalfWidth+0x6a>
 8800bc2:	464a      	mov	r2, r9
 8800bc4:	20fc      	movs	r0, #252	@ 0xfc
 8800bc6:	7811      	ldrb	r1, [r2, #0]
 8800bc8:	7832      	ldrb	r2, [r6, #0]
 8800bca:	0080      	lsls	r0, r0, #2
 8800bcc:	0112      	lsls	r2, r2, #4
 8800bce:	4002      	ands	r2, r0
 8800bd0:	4650      	mov	r0, sl
 8800bd2:	0207      	lsls	r7, r0, #8
 8800bd4:	2008      	movs	r0, #8
 8800bd6:	433a      	orrs	r2, r7
 8800bd8:	4302      	orrs	r2, r0
 8800bda:	9201      	str	r2, [sp, #4]
 8800bdc:	9000      	str	r0, [sp, #0]
 8800bde:	2208      	movs	r2, #8
 8800be0:	4640      	mov	r0, r8
 8800be2:	f7ff fb3b 	bl	880025c <chs_emit.isra.0>
 8800be6:	2001      	movs	r0, #1
 8800be8:	e7bb      	b.n	8800b62 <DrawHalfWidth+0x1a>
 8800bea:	46c0      	nop			@ (mov r8, r8)
 8800bec:	091e0000 	.word	0x091e0000

08800bf0 <DrawGlyph>:
 8800bf0:	b570      	push	{r4, r5, r6, lr}
 8800bf2:	0005      	movs	r5, r0
 8800bf4:	000c      	movs	r4, r1
 8800bf6:	29f6      	cmp	r1, #246	@ 0xf6
 8800bf8:	d903      	bls.n	8800c02 <DrawGlyph+0x12>
 8800bfa:	2001      	movs	r0, #1
 8800bfc:	bc70      	pop	{r4, r5, r6}
 8800bfe:	bc02      	pop	{r1}
 8800c00:	4708      	bx	r1
 8800c02:	f7ff ffa1 	bl	8800b48 <DrawHalfWidth>
 8800c06:	2800      	cmp	r0, #0
 8800c08:	d1f7      	bne.n	8800bfa <DrawGlyph+0xa>
 8800c0a:	0021      	movs	r1, r4
 8800c0c:	0028      	movs	r0, r5
 8800c0e:	f7ff fecb 	bl	88009a8 <DrawGlyph.part.0>
 8800c12:	e7f2      	b.n	8800bfa <DrawGlyph+0xa>

08800c14 <PrintNextChar_Hook>:
 8800c14:	b570      	push	{r4, r5, r6, lr}
 8800c16:	1e04      	subs	r4, r0, #0
 8800c18:	d042      	beq.n	8800ca0 <PrintNextChar_Hook+0x8c>
 8800c1a:	7d43      	ldrb	r3, [r0, #21]
 8800c1c:	7d02      	ldrb	r2, [r0, #20]
 8800c1e:	021b      	lsls	r3, r3, #8
 8800c20:	4313      	orrs	r3, r2
 8800c22:	7c42      	ldrb	r2, [r0, #17]
 8800c24:	7c01      	ldrb	r1, [r0, #16]
 8800c26:	0212      	lsls	r2, r2, #8
 8800c28:	430a      	orrs	r2, r1
 8800c2a:	7c81      	ldrb	r1, [r0, #18]
 8800c2c:	0409      	lsls	r1, r1, #16
 8800c2e:	4311      	orrs	r1, r2
 8800c30:	7cc2      	ldrb	r2, [r0, #19]
 8800c32:	0612      	lsls	r2, r2, #24
 8800c34:	430a      	orrs	r2, r1
 8800c36:	5cd5      	ldrb	r5, [r2, r3]
 8800c38:	2df9      	cmp	r5, #249	@ 0xf9
 8800c3a:	d81e      	bhi.n	8800c7a <PrintNextChar_Hook+0x66>
 8800c3c:	3301      	adds	r3, #1
 8800c3e:	041a      	lsls	r2, r3, #16
 8800c40:	0e12      	lsrs	r2, r2, #24
 8800c42:	7503      	strb	r3, [r0, #20]
 8800c44:	7542      	strb	r2, [r0, #21]
 8800c46:	4b1f      	ldr	r3, [pc, #124]	@ (8800cc4 <PrintNextChar_Hook+0xb0>)
 8800c48:	781b      	ldrb	r3, [r3, #0]
 8800c4a:	2b00      	cmp	r3, #0
 8800c4c:	d003      	beq.n	8800c56 <PrintNextChar_Hook+0x42>
 8800c4e:	2001      	movs	r0, #1
 8800c50:	bc70      	pop	{r4, r5, r6}
 8800c52:	bc02      	pop	{r1}
 8800c54:	4708      	bx	r1
 8800c56:	0029      	movs	r1, r5
 8800c58:	f000 fe78 	bl	880194c <TranslateHandleChar>
 8800c5c:	2df6      	cmp	r5, #246	@ 0xf6
 8800c5e:	d8f6      	bhi.n	8800c4e <PrintNextChar_Hook+0x3a>
 8800c60:	2800      	cmp	r0, #0
 8800c62:	d1f4      	bne.n	8800c4e <PrintNextChar_Hook+0x3a>
 8800c64:	0029      	movs	r1, r5
 8800c66:	0020      	movs	r0, r4
 8800c68:	f7ff ff6e 	bl	8800b48 <DrawHalfWidth>
 8800c6c:	2800      	cmp	r0, #0
 8800c6e:	d1ee      	bne.n	8800c4e <PrintNextChar_Hook+0x3a>
 8800c70:	0029      	movs	r1, r5
 8800c72:	0020      	movs	r0, r4
 8800c74:	f7ff fe98 	bl	88009a8 <DrawGlyph.part.0>
 8800c78:	e7e9      	b.n	8800c4e <PrintNextChar_Hook+0x3a>
 8800c7a:	1dab      	adds	r3, r5, #6
 8800c7c:	061b      	lsls	r3, r3, #24
 8800c7e:	0e1b      	lsrs	r3, r3, #24
 8800c80:	2b01      	cmp	r3, #1
 8800c82:	d905      	bls.n	8800c90 <PrintNextChar_Hook+0x7c>
 8800c84:	2dfe      	cmp	r5, #254	@ 0xfe
 8800c86:	d008      	beq.n	8800c9a <PrintNextChar_Hook+0x86>
 8800c88:	0020      	movs	r0, r4
 8800c8a:	f7ff f9bd 	bl	8800008 <PrintNextChar_Origin>
 8800c8e:	e7df      	b.n	8800c50 <PrintNextChar_Hook+0x3c>
 8800c90:	f000 f962 	bl	8800f58 <v8_phase_get>
 8800c94:	2307      	movs	r3, #7
 8800c96:	4203      	tst	r3, r0
 8800c98:	d104      	bne.n	8800ca4 <PrintNextChar_Hook+0x90>
 8800c9a:	f000 f98d 	bl	8800fb8 <v8_phase_reset>
 8800c9e:	e7f3      	b.n	8800c88 <PrintNextChar_Hook+0x74>
 8800ca0:	2000      	movs	r0, #0
 8800ca2:	e7d5      	b.n	8800c50 <PrintNextChar_Hook+0x3c>
 8800ca4:	7ee2      	ldrb	r2, [r4, #27]
 8800ca6:	3201      	adds	r2, #1
 8800ca8:	76e2      	strb	r2, [r4, #27]
 8800caa:	7aa2      	ldrb	r2, [r4, #10]
 8800cac:	4213      	tst	r3, r2
 8800cae:	d1f4      	bne.n	8800c9a <PrintNextChar_Hook+0x86>
 8800cb0:	7e63      	ldrb	r3, [r4, #25]
 8800cb2:	7e22      	ldrb	r2, [r4, #24]
 8800cb4:	021b      	lsls	r3, r3, #8
 8800cb6:	4313      	orrs	r3, r2
 8800cb8:	3302      	adds	r3, #2
 8800cba:	041a      	lsls	r2, r3, #16
 8800cbc:	0e12      	lsrs	r2, r2, #24
 8800cbe:	7623      	strb	r3, [r4, #24]
 8800cc0:	7662      	strb	r2, [r4, #25]
 8800cc2:	e7ea      	b.n	8800c9a <PrintNextChar_Hook+0x86>
 8800cc4:	0203feb8 	.word	0x0203feb8
 8800cc8:	4718      	bx	r3
 8800cca:	4720      	bx	r4
 8800ccc:	4728      	bx	r5
 8800cce:	46c0      	nop			@ (mov r8, r8)

08800cd0 <blend_glyph_4bpp>:
 8800cd0:	b5f0      	push	{r4, r5, r6, r7, lr}
 8800cd2:	46de      	mov	lr, fp
 8800cd4:	464e      	mov	r6, r9
 8800cd6:	4657      	mov	r7, sl
 8800cd8:	4645      	mov	r5, r8
 8800cda:	b5e0      	push	{r5, r6, r7, lr}
 8800cdc:	4684      	mov	ip, r0
 8800cde:	468b      	mov	fp, r1
 8800ce0:	0016      	movs	r6, r2
 8800ce2:	b099      	sub	sp, #100	@ 0x64
 8800ce4:	2b00      	cmp	r3, #0
 8800ce6:	d10a      	bne.n	8800cfe <blend_glyph_4bpp+0x2e>
 8800ce8:	9b22      	ldr	r3, [sp, #136]	@ 0x88
 8800cea:	08d8      	lsrs	r0, r3, #3
 8800cec:	b019      	add	sp, #100	@ 0x64
 8800cee:	bcf0      	pop	{r4, r5, r6, r7}
 8800cf0:	46bb      	mov	fp, r7
 8800cf2:	46b2      	mov	sl, r6
 8800cf4:	46a9      	mov	r9, r5
 8800cf6:	46a0      	mov	r8, r4
 8800cf8:	bcf0      	pop	{r4, r5, r6, r7}
 8800cfa:	bc02      	pop	{r1}
 8800cfc:	4708      	bx	r1
 8800cfe:	001c      	movs	r4, r3
 8800d00:	2b08      	cmp	r3, #8
 8800d02:	d900      	bls.n	8800d06 <blend_glyph_4bpp+0x36>
 8800d04:	2408      	movs	r4, #8
 8800d06:	9b22      	ldr	r3, [sp, #136]	@ 0x88
 8800d08:	2b07      	cmp	r3, #7
 8800d0a:	d900      	bls.n	8800d0e <blend_glyph_4bpp+0x3e>
 8800d0c:	2307      	movs	r3, #7
 8800d0e:	005a      	lsls	r2, r3, #1
 8800d10:	0061      	lsls	r1, r4, #1
 8800d12:	18d2      	adds	r2, r2, r3
 8800d14:	1909      	adds	r1, r1, r4
 8800d16:	0149      	lsls	r1, r1, #5
 8800d18:	0092      	lsls	r2, r2, #2
 8800d1a:	1852      	adds	r2, r2, r1
 8800d1c:	4947      	ldr	r1, [pc, #284]	@ (8800e3c <blend_glyph_4bpp+0x16c>)
 8800d1e:	1852      	adds	r2, r2, r1
 8800d20:	6891      	ldr	r1, [r2, #8]
 8800d22:	6810      	ldr	r0, [r2, #0]
 8800d24:	6852      	ldr	r2, [r2, #4]
 8800d26:	9205      	str	r2, [sp, #20]
 8800d28:	465a      	mov	r2, fp
 8800d2a:	4308      	orrs	r0, r1
 8800d2c:	18e1      	adds	r1, r4, r3
 8800d2e:	9003      	str	r0, [sp, #12]
 8800d30:	9107      	str	r1, [sp, #28]
 8800d32:	2a00      	cmp	r2, #0
 8800d34:	d07f      	beq.n	8800e36 <blend_glyph_4bpp+0x166>
 8800d36:	2208      	movs	r2, #8
 8800d38:	428a      	cmp	r2, r1
 8800d3a:	4192      	sbcs	r2, r2
 8800d3c:	4252      	negs	r2, r2
 8800d3e:	9202      	str	r2, [sp, #8]
 8800d40:	4a3f      	ldr	r2, [pc, #252]	@ (8800e40 <blend_glyph_4bpp+0x170>)
 8800d42:	00db      	lsls	r3, r3, #3
 8800d44:	58d0      	ldr	r0, [r2, r3]
 8800d46:	9004      	str	r0, [sp, #16]
 8800d48:	a810      	add	r0, sp, #64	@ 0x40
 8800d4a:	4682      	mov	sl, r0
 8800d4c:	2000      	movs	r0, #0
 8800d4e:	4680      	mov	r8, r0
 8800d50:	18d3      	adds	r3, r2, r3
 8800d52:	9306      	str	r3, [sp, #24]
 8800d54:	4643      	mov	r3, r8
 8800d56:	9301      	str	r3, [sp, #4]
 8800d58:	0033      	movs	r3, r6
 8800d5a:	a908      	add	r1, sp, #32
 8800d5c:	465e      	mov	r6, fp
 8800d5e:	4689      	mov	r9, r1
 8800d60:	270f      	movs	r7, #15
 8800d62:	469b      	mov	fp, r3
 8800d64:	3001      	adds	r0, #1
 8800d66:	2100      	movs	r1, #0
 8800d68:	2300      	movs	r3, #0
 8800d6a:	46b0      	mov	r8, r6
 8800d6c:	9d01      	ldr	r5, [sp, #4]
 8800d6e:	445d      	add	r5, fp
 8800d70:	0006      	movs	r6, r0
 8800d72:	085a      	lsrs	r2, r3, #1
 8800d74:	401e      	ands	r6, r3
 8800d76:	5caa      	ldrb	r2, [r5, r2]
 8800d78:	00b6      	lsls	r6, r6, #2
 8800d7a:	4132      	asrs	r2, r6
 8800d7c:	9e23      	ldr	r6, [sp, #140]	@ 0x8c
 8800d7e:	403a      	ands	r2, r7
 8800d80:	5cb2      	ldrb	r2, [r6, r2]
 8800d82:	009e      	lsls	r6, r3, #2
 8800d84:	40b2      	lsls	r2, r6
 8800d86:	3301      	adds	r3, #1
 8800d88:	4311      	orrs	r1, r2
 8800d8a:	429c      	cmp	r4, r3
 8800d8c:	d1f0      	bne.n	8800d70 <blend_glyph_4bpp+0xa0>
 8800d8e:	4663      	mov	r3, ip
 8800d90:	9d01      	ldr	r5, [sp, #4]
 8800d92:	9a03      	ldr	r2, [sp, #12]
 8800d94:	595b      	ldr	r3, [r3, r5]
 8800d96:	4013      	ands	r3, r2
 8800d98:	4646      	mov	r6, r8
 8800d9a:	000a      	movs	r2, r1
 8800d9c:	4698      	mov	r8, r3
 8800d9e:	9b04      	ldr	r3, [sp, #16]
 8800da0:	409a      	lsls	r2, r3
 8800da2:	4643      	mov	r3, r8
 8800da4:	4313      	orrs	r3, r2
 8800da6:	464a      	mov	r2, r9
 8800da8:	6013      	str	r3, [r2, #0]
 8800daa:	9b02      	ldr	r3, [sp, #8]
 8800dac:	2b00      	cmp	r3, #0
 8800dae:	d008      	beq.n	8800dc2 <blend_glyph_4bpp+0xf2>
 8800db0:	9a05      	ldr	r2, [sp, #20]
 8800db2:	5973      	ldr	r3, [r6, r5]
 8800db4:	4013      	ands	r3, r2
 8800db6:	9a06      	ldr	r2, [sp, #24]
 8800db8:	6852      	ldr	r2, [r2, #4]
 8800dba:	40d1      	lsrs	r1, r2
 8800dbc:	4652      	mov	r2, sl
 8800dbe:	430b      	orrs	r3, r1
 8800dc0:	6013      	str	r3, [r2, #0]
 8800dc2:	2304      	movs	r3, #4
 8800dc4:	4698      	mov	r8, r3
 8800dc6:	9b01      	ldr	r3, [sp, #4]
 8800dc8:	3304      	adds	r3, #4
 8800dca:	9301      	str	r3, [sp, #4]
 8800dcc:	44c2      	add	sl, r8
 8800dce:	44c1      	add	r9, r8
 8800dd0:	2b20      	cmp	r3, #32
 8800dd2:	d1c8      	bne.n	8800d66 <blend_glyph_4bpp+0x96>
 8800dd4:	9908      	ldr	r1, [sp, #32]
 8800dd6:	9b0f      	ldr	r3, [sp, #60]	@ 0x3c
 8800dd8:	4688      	mov	r8, r1
 8800dda:	4699      	mov	r9, r3
 8800ddc:	4661      	mov	r1, ip
 8800dde:	4643      	mov	r3, r8
 8800de0:	9a0e      	ldr	r2, [sp, #56]	@ 0x38
 8800de2:	618a      	str	r2, [r1, #24]
 8800de4:	464a      	mov	r2, r9
 8800de6:	46b3      	mov	fp, r6
 8800de8:	9f09      	ldr	r7, [sp, #36]	@ 0x24
 8800dea:	9e0a      	ldr	r6, [sp, #40]	@ 0x28
 8800dec:	9d0b      	ldr	r5, [sp, #44]	@ 0x2c
 8800dee:	9c0c      	ldr	r4, [sp, #48]	@ 0x30
 8800df0:	980d      	ldr	r0, [sp, #52]	@ 0x34
 8800df2:	600b      	str	r3, [r1, #0]
 8800df4:	9b02      	ldr	r3, [sp, #8]
 8800df6:	604f      	str	r7, [r1, #4]
 8800df8:	608e      	str	r6, [r1, #8]
 8800dfa:	60cd      	str	r5, [r1, #12]
 8800dfc:	610c      	str	r4, [r1, #16]
 8800dfe:	6148      	str	r0, [r1, #20]
 8800e00:	61ca      	str	r2, [r1, #28]
 8800e02:	2b00      	cmp	r3, #0
 8800e04:	d014      	beq.n	8800e30 <blend_glyph_4bpp+0x160>
 8800e06:	9b17      	ldr	r3, [sp, #92]	@ 0x5c
 8800e08:	9910      	ldr	r1, [sp, #64]	@ 0x40
 8800e0a:	4698      	mov	r8, r3
 8800e0c:	468c      	mov	ip, r1
 8800e0e:	4659      	mov	r1, fp
 8800e10:	9a16      	ldr	r2, [sp, #88]	@ 0x58
 8800e12:	4663      	mov	r3, ip
 8800e14:	618a      	str	r2, [r1, #24]
 8800e16:	4642      	mov	r2, r8
 8800e18:	9f11      	ldr	r7, [sp, #68]	@ 0x44
 8800e1a:	9e12      	ldr	r6, [sp, #72]	@ 0x48
 8800e1c:	9d13      	ldr	r5, [sp, #76]	@ 0x4c
 8800e1e:	9c14      	ldr	r4, [sp, #80]	@ 0x50
 8800e20:	9815      	ldr	r0, [sp, #84]	@ 0x54
 8800e22:	600b      	str	r3, [r1, #0]
 8800e24:	604f      	str	r7, [r1, #4]
 8800e26:	608e      	str	r6, [r1, #8]
 8800e28:	60cd      	str	r5, [r1, #12]
 8800e2a:	610c      	str	r4, [r1, #16]
 8800e2c:	6148      	str	r0, [r1, #20]
 8800e2e:	61ca      	str	r2, [r1, #28]
 8800e30:	9b07      	ldr	r3, [sp, #28]
 8800e32:	08d8      	lsrs	r0, r3, #3
 8800e34:	e75a      	b.n	8800cec <blend_glyph_4bpp+0x1c>
 8800e36:	2200      	movs	r2, #0
 8800e38:	9202      	str	r2, [sp, #8]
 8800e3a:	e781      	b.n	8800d40 <blend_glyph_4bpp+0x70>
 8800e3c:	0880204c 	.word	0x0880204c
 8800e40:	0880200c 	.word	0x0880200c

08800e44 <extract_cols>:
 8800e44:	b5f0      	push	{r4, r5, r6, r7, lr}
 8800e46:	464e      	mov	r6, r9
 8800e48:	46de      	mov	lr, fp
 8800e4a:	4657      	mov	r7, sl
 8800e4c:	4645      	mov	r5, r8
 8800e4e:	b5e0      	push	{r5, r6, r7, lr}
 8800e50:	b089      	sub	sp, #36	@ 0x24
 8800e52:	000c      	movs	r4, r1
 8800e54:	9006      	str	r0, [sp, #24]
 8800e56:	2100      	movs	r1, #0
 8800e58:	2000      	movs	r0, #0
 8800e5a:	9e12      	ldr	r6, [sp, #72]	@ 0x48
 8800e5c:	5458      	strb	r0, [r3, r1]
 8800e5e:	5470      	strb	r0, [r6, r1]
 8800e60:	3101      	adds	r1, #1
 8800e62:	2920      	cmp	r1, #32
 8800e64:	d1fa      	bne.n	8800e5c <extract_cols+0x18>
 8800e66:	2a00      	cmp	r2, #0
 8800e68:	d069      	beq.n	8800f3e <extract_cols+0xfa>
 8800e6a:	9906      	ldr	r1, [sp, #24]
 8800e6c:	0008      	movs	r0, r1
 8800e6e:	3020      	adds	r0, #32
 8800e70:	9007      	str	r0, [sp, #28]
 8800e72:	3160      	adds	r1, #96	@ 0x60
 8800e74:	3020      	adds	r0, #32
 8800e76:	4693      	mov	fp, r2
 8800e78:	9004      	str	r0, [sp, #16]
 8800e7a:	9105      	str	r1, [sp, #20]
 8800e7c:	2a08      	cmp	r2, #8
 8800e7e:	d867      	bhi.n	8800f50 <extract_cols+0x10c>
 8800e80:	465a      	mov	r2, fp
 8800e82:	2500      	movs	r5, #0
 8800e84:	270f      	movs	r7, #15
 8800e86:	0020      	movs	r0, r4
 8800e88:	9202      	str	r2, [sp, #8]
 8800e8a:	e004      	b.n	8800e96 <extract_cols+0x52>
 8800e8c:	9a02      	ldr	r2, [sp, #8]
 8800e8e:	3501      	adds	r5, #1
 8800e90:	3001      	adds	r0, #1
 8800e92:	42aa      	cmp	r2, r5
 8800e94:	d053      	beq.n	8800f3e <extract_cols+0xfa>
 8800e96:	280f      	cmp	r0, #15
 8800e98:	d8f8      	bhi.n	8800e8c <extract_cols+0x48>
 8800e9a:	9a04      	ldr	r2, [sp, #16]
 8800e9c:	9c05      	ldr	r4, [sp, #20]
 8800e9e:	4694      	mov	ip, r2
 8800ea0:	2807      	cmp	r0, #7
 8800ea2:	d802      	bhi.n	8800eaa <extract_cols+0x66>
 8800ea4:	9a06      	ldr	r2, [sp, #24]
 8800ea6:	4694      	mov	ip, r2
 8800ea8:	9c07      	ldr	r4, [sp, #28]
 8800eaa:	2203      	movs	r2, #3
 8800eac:	0841      	lsrs	r1, r0, #1
 8800eae:	4011      	ands	r1, r2
 8800eb0:	468b      	mov	fp, r1
 8800eb2:	2101      	movs	r1, #1
 8800eb4:	4001      	ands	r1, r0
 8800eb6:	468a      	mov	sl, r1
 8800eb8:	2101      	movs	r1, #1
 8800eba:	4029      	ands	r1, r5
 8800ebc:	4689      	mov	r9, r1
 8800ebe:	2120      	movs	r1, #32
 8800ec0:	4688      	mov	r8, r1
 8800ec2:	4659      	mov	r1, fp
 8800ec4:	086a      	lsrs	r2, r5, #1
 8800ec6:	1a89      	subs	r1, r1, r2
 8800ec8:	4490      	add	r8, r2
 8800eca:	1864      	adds	r4, r4, r1
 8800ecc:	448c      	add	ip, r1
 8800ece:	4641      	mov	r1, r8
 8800ed0:	4683      	mov	fp, r0
 8800ed2:	46a0      	mov	r8, r4
 8800ed4:	9503      	str	r5, [sp, #12]
 8800ed6:	9101      	str	r1, [sp, #4]
 8800ed8:	e012      	b.n	8800f00 <extract_cols+0xbc>
 8800eda:	4648      	mov	r0, r9
 8800edc:	5c9c      	ldrb	r4, [r3, r2]
 8800ede:	092d      	lsrs	r5, r5, #4
 8800ee0:	0909      	lsrs	r1, r1, #4
 8800ee2:	2800      	cmp	r0, #0
 8800ee4:	d019      	beq.n	8800f1a <extract_cols+0xd6>
 8800ee6:	403c      	ands	r4, r7
 8800ee8:	012d      	lsls	r5, r5, #4
 8800eea:	432c      	orrs	r4, r5
 8800eec:	549c      	strb	r4, [r3, r2]
 8800eee:	5cb4      	ldrb	r4, [r6, r2]
 8800ef0:	0109      	lsls	r1, r1, #4
 8800ef2:	403c      	ands	r4, r7
 8800ef4:	4321      	orrs	r1, r4
 8800ef6:	54b1      	strb	r1, [r6, r2]
 8800ef8:	9901      	ldr	r1, [sp, #4]
 8800efa:	3204      	adds	r2, #4
 8800efc:	4291      	cmp	r1, r2
 8800efe:	d017      	beq.n	8800f30 <extract_cols+0xec>
 8800f00:	4661      	mov	r1, ip
 8800f02:	4654      	mov	r4, sl
 8800f04:	5c8d      	ldrb	r5, [r1, r2]
 8800f06:	4641      	mov	r1, r8
 8800f08:	5c89      	ldrb	r1, [r1, r2]
 8800f0a:	2c00      	cmp	r4, #0
 8800f0c:	d1e5      	bne.n	8800eda <extract_cols+0x96>
 8800f0e:	4648      	mov	r0, r9
 8800f10:	5c9c      	ldrb	r4, [r3, r2]
 8800f12:	403d      	ands	r5, r7
 8800f14:	4039      	ands	r1, r7
 8800f16:	2800      	cmp	r0, #0
 8800f18:	d1e5      	bne.n	8800ee6 <extract_cols+0xa2>
 8800f1a:	43bc      	bics	r4, r7
 8800f1c:	4325      	orrs	r5, r4
 8800f1e:	549d      	strb	r5, [r3, r2]
 8800f20:	5cb4      	ldrb	r4, [r6, r2]
 8800f22:	43bc      	bics	r4, r7
 8800f24:	4321      	orrs	r1, r4
 8800f26:	54b1      	strb	r1, [r6, r2]
 8800f28:	9901      	ldr	r1, [sp, #4]
 8800f2a:	3204      	adds	r2, #4
 8800f2c:	4291      	cmp	r1, r2
 8800f2e:	d1e7      	bne.n	8800f00 <extract_cols+0xbc>
 8800f30:	4658      	mov	r0, fp
 8800f32:	9d03      	ldr	r5, [sp, #12]
 8800f34:	9a02      	ldr	r2, [sp, #8]
 8800f36:	3501      	adds	r5, #1
 8800f38:	3001      	adds	r0, #1
 8800f3a:	42aa      	cmp	r2, r5
 8800f3c:	d1ab      	bne.n	8800e96 <extract_cols+0x52>
 8800f3e:	b009      	add	sp, #36	@ 0x24
 8800f40:	bcf0      	pop	{r4, r5, r6, r7}
 8800f42:	46bb      	mov	fp, r7
 8800f44:	46b2      	mov	sl, r6
 8800f46:	46a9      	mov	r9, r5
 8800f48:	46a0      	mov	r8, r4
 8800f4a:	bcf0      	pop	{r4, r5, r6, r7}
 8800f4c:	bc01      	pop	{r0}
 8800f4e:	4700      	bx	r0
 8800f50:	2208      	movs	r2, #8
 8800f52:	4693      	mov	fp, r2
 8800f54:	e794      	b.n	8800e80 <extract_cols+0x3c>
 8800f56:	46c0      	nop			@ (mov r8, r8)

08800f58 <v8_phase_get>:
 8800f58:	7843      	ldrb	r3, [r0, #1]
 8800f5a:	7802      	ldrb	r2, [r0, #0]
 8800f5c:	021b      	lsls	r3, r3, #8
 8800f5e:	4313      	orrs	r3, r2
 8800f60:	7882      	ldrb	r2, [r0, #2]
 8800f62:	0412      	lsls	r2, r2, #16
 8800f64:	431a      	orrs	r2, r3
 8800f66:	78c3      	ldrb	r3, [r0, #3]
 8800f68:	061b      	lsls	r3, r3, #24
 8800f6a:	4313      	orrs	r3, r2
 8800f6c:	2200      	movs	r2, #0
 8800f6e:	2b00      	cmp	r3, #0
 8800f70:	d009      	beq.n	8800f86 <v8_phase_get+0x2e>
 8800f72:	0882      	lsrs	r2, r0, #2
 8800f74:	08db      	lsrs	r3, r3, #3
 8800f76:	4053      	eors	r3, r2
 8800f78:	7f42      	ldrb	r2, [r0, #29]
 8800f7a:	405a      	eors	r2, r3
 8800f7c:	7f03      	ldrb	r3, [r0, #28]
 8800f7e:	021b      	lsls	r3, r3, #8
 8800f80:	405a      	eors	r2, r3
 8800f82:	0412      	lsls	r2, r2, #16
 8800f84:	0c12      	lsrs	r2, r2, #16
 8800f86:	4b05      	ldr	r3, [pc, #20]	@ (8800f9c <v8_phase_get+0x44>)
 8800f88:	8819      	ldrh	r1, [r3, #0]
 8800f8a:	4291      	cmp	r1, r2
 8800f8c:	d003      	beq.n	8800f96 <v8_phase_get+0x3e>
 8800f8e:	801a      	strh	r2, [r3, #0]
 8800f90:	2200      	movs	r2, #0
 8800f92:	4b03      	ldr	r3, [pc, #12]	@ (8800fa0 <v8_phase_get+0x48>)
 8800f94:	801a      	strh	r2, [r3, #0]
 8800f96:	4b02      	ldr	r3, [pc, #8]	@ (8800fa0 <v8_phase_get+0x48>)
 8800f98:	8818      	ldrh	r0, [r3, #0]
 8800f9a:	4770      	bx	lr
 8800f9c:	0203ff46 	.word	0x0203ff46
 8800fa0:	0203ff44 	.word	0x0203ff44

08800fa4 <v8_phase_advance>:
 8800fa4:	4a03      	ldr	r2, [pc, #12]	@ (8800fb4 <v8_phase_advance+0x10>)
 8800fa6:	8813      	ldrh	r3, [r2, #0]
 8800fa8:	181b      	adds	r3, r3, r0
 8800faa:	041b      	lsls	r3, r3, #16
 8800fac:	0c1b      	lsrs	r3, r3, #16
 8800fae:	8013      	strh	r3, [r2, #0]
 8800fb0:	4770      	bx	lr
 8800fb2:	46c0      	nop			@ (mov r8, r8)
 8800fb4:	0203ff44 	.word	0x0203ff44

08800fb8 <v8_phase_reset>:
 8800fb8:	2300      	movs	r3, #0
 8800fba:	4a02      	ldr	r2, [pc, #8]	@ (8800fc4 <v8_phase_reset+0xc>)
 8800fbc:	8013      	strh	r3, [r2, #0]
 8800fbe:	4a02      	ldr	r2, [pc, #8]	@ (8800fc8 <v8_phase_reset+0x10>)
 8800fc0:	8013      	strh	r3, [r2, #0]
 8800fc2:	4770      	bx	lr
 8800fc4:	0203ff44 	.word	0x0203ff44
 8800fc8:	0203ff46 	.word	0x0203ff46

08800fcc <chs_canvas_init_once>:
 8800fcc:	4b10      	ldr	r3, [pc, #64]	@ (8801010 <chs_canvas_init_once+0x44>)
 8800fce:	4a11      	ldr	r2, [pc, #68]	@ (8801014 <chs_canvas_init_once+0x48>)
 8800fd0:	8819      	ldrh	r1, [r3, #0]
 8800fd2:	4291      	cmp	r1, r2
 8800fd4:	d01b      	beq.n	880100e <chs_canvas_init_once+0x42>
 8800fd6:	801a      	strh	r2, [r3, #0]
 8800fd8:	2300      	movs	r3, #0
 8800fda:	4a0f      	ldr	r2, [pc, #60]	@ (8801018 <chs_canvas_init_once+0x4c>)
 8800fdc:	6013      	str	r3, [r2, #0]
 8800fde:	4a0f      	ldr	r2, [pc, #60]	@ (880101c <chs_canvas_init_once+0x50>)
 8800fe0:	8013      	strh	r3, [r2, #0]
 8800fe2:	4a0f      	ldr	r2, [pc, #60]	@ (8801020 <chs_canvas_init_once+0x54>)
 8800fe4:	6013      	str	r3, [r2, #0]
 8800fe6:	4a0f      	ldr	r2, [pc, #60]	@ (8801024 <chs_canvas_init_once+0x58>)
 8800fe8:	8013      	strh	r3, [r2, #0]
 8800fea:	4a0f      	ldr	r2, [pc, #60]	@ (8801028 <chs_canvas_init_once+0x5c>)
 8800fec:	6013      	str	r3, [r2, #0]
 8800fee:	4a0f      	ldr	r2, [pc, #60]	@ (880102c <chs_canvas_init_once+0x60>)
 8800ff0:	8013      	strh	r3, [r2, #0]
 8800ff2:	4a0f      	ldr	r2, [pc, #60]	@ (8801030 <chs_canvas_init_once+0x64>)
 8800ff4:	6013      	str	r3, [r2, #0]
 8800ff6:	4a0f      	ldr	r2, [pc, #60]	@ (8801034 <chs_canvas_init_once+0x68>)
 8800ff8:	8013      	strh	r3, [r2, #0]
 8800ffa:	4a0f      	ldr	r2, [pc, #60]	@ (8801038 <chs_canvas_init_once+0x6c>)
 8800ffc:	6013      	str	r3, [r2, #0]
 8800ffe:	4a0f      	ldr	r2, [pc, #60]	@ (880103c <chs_canvas_init_once+0x70>)
 8801000:	8013      	strh	r3, [r2, #0]
 8801002:	4a0f      	ldr	r2, [pc, #60]	@ (8801040 <chs_canvas_init_once+0x74>)
 8801004:	6013      	str	r3, [r2, #0]
 8801006:	4a0f      	ldr	r2, [pc, #60]	@ (8801044 <chs_canvas_init_once+0x78>)
 8801008:	8013      	strh	r3, [r2, #0]
 880100a:	4a0f      	ldr	r2, [pc, #60]	@ (8801048 <chs_canvas_init_once+0x7c>)
 880100c:	8013      	strh	r3, [r2, #0]
 880100e:	4770      	bx	lr
 8801010:	0203ff82 	.word	0x0203ff82
 8801014:	000021c7 	.word	0x000021c7
 8801018:	0203ff50 	.word	0x0203ff50
 880101c:	0203ff68 	.word	0x0203ff68
 8801020:	0203ff54 	.word	0x0203ff54
 8801024:	0203ff6a 	.word	0x0203ff6a
 8801028:	0203ff58 	.word	0x0203ff58
 880102c:	0203ff6c 	.word	0x0203ff6c
 8801030:	0203ff5c 	.word	0x0203ff5c
 8801034:	0203ff6e 	.word	0x0203ff6e
 8801038:	0203ff60 	.word	0x0203ff60
 880103c:	0203ff70 	.word	0x0203ff70
 8801040:	0203ff64 	.word	0x0203ff64
 8801044:	0203ff72 	.word	0x0203ff72
 8801048:	0203ff80 	.word	0x0203ff80

0880104c <chs_canvas_base_for>:
 880104c:	0001      	movs	r1, r0
 880104e:	b530      	push	{r4, r5, lr}
 8801050:	2800      	cmp	r0, #0
 8801052:	d100      	bne.n	8801056 <chs_canvas_base_for+0xa>
 8801054:	e06b      	b.n	880112e <chs_canvas_base_for+0xe2>
 8801056:	4b3a      	ldr	r3, [pc, #232]	@ (8801140 <chs_canvas_base_for+0xf4>)
 8801058:	4a3a      	ldr	r2, [pc, #232]	@ (8801144 <chs_canvas_base_for+0xf8>)
 880105a:	8818      	ldrh	r0, [r3, #0]
 880105c:	4290      	cmp	r0, r2
 880105e:	d01b      	beq.n	8801098 <chs_canvas_base_for+0x4c>
 8801060:	801a      	strh	r2, [r3, #0]
 8801062:	2300      	movs	r3, #0
 8801064:	4a38      	ldr	r2, [pc, #224]	@ (8801148 <chs_canvas_base_for+0xfc>)
 8801066:	6013      	str	r3, [r2, #0]
 8801068:	4a38      	ldr	r2, [pc, #224]	@ (880114c <chs_canvas_base_for+0x100>)
 880106a:	8013      	strh	r3, [r2, #0]
 880106c:	4a38      	ldr	r2, [pc, #224]	@ (8801150 <chs_canvas_base_for+0x104>)
 880106e:	6013      	str	r3, [r2, #0]
 8801070:	4a38      	ldr	r2, [pc, #224]	@ (8801154 <chs_canvas_base_for+0x108>)
 8801072:	8013      	strh	r3, [r2, #0]
 8801074:	4a38      	ldr	r2, [pc, #224]	@ (8801158 <chs_canvas_base_for+0x10c>)
 8801076:	6013      	str	r3, [r2, #0]
 8801078:	4a38      	ldr	r2, [pc, #224]	@ (880115c <chs_canvas_base_for+0x110>)
 880107a:	8013      	strh	r3, [r2, #0]
 880107c:	4a38      	ldr	r2, [pc, #224]	@ (8801160 <chs_canvas_base_for+0x114>)
 880107e:	6013      	str	r3, [r2, #0]
 8801080:	4a38      	ldr	r2, [pc, #224]	@ (8801164 <chs_canvas_base_for+0x118>)
 8801082:	8013      	strh	r3, [r2, #0]
 8801084:	4a38      	ldr	r2, [pc, #224]	@ (8801168 <chs_canvas_base_for+0x11c>)
 8801086:	6013      	str	r3, [r2, #0]
 8801088:	4a38      	ldr	r2, [pc, #224]	@ (880116c <chs_canvas_base_for+0x120>)
 880108a:	8013      	strh	r3, [r2, #0]
 880108c:	4a38      	ldr	r2, [pc, #224]	@ (8801170 <chs_canvas_base_for+0x124>)
 880108e:	6013      	str	r3, [r2, #0]
 8801090:	4a38      	ldr	r2, [pc, #224]	@ (8801174 <chs_canvas_base_for+0x128>)
 8801092:	8013      	strh	r3, [r2, #0]
 8801094:	4a38      	ldr	r2, [pc, #224]	@ (8801178 <chs_canvas_base_for+0x12c>)
 8801096:	8013      	strh	r3, [r2, #0]
 8801098:	2300      	movs	r3, #0
 880109a:	482b      	ldr	r0, [pc, #172]	@ (8801148 <chs_canvas_base_for+0xfc>)
 880109c:	4684      	mov	ip, r0
 880109e:	009a      	lsls	r2, r3, #2
 88010a0:	4462      	add	r2, ip
 88010a2:	6812      	ldr	r2, [r2, #0]
 88010a4:	4291      	cmp	r1, r2
 88010a6:	d044      	beq.n	8801132 <chs_canvas_base_for+0xe6>
 88010a8:	3301      	adds	r3, #1
 88010aa:	2b06      	cmp	r3, #6
 88010ac:	d1f5      	bne.n	880109a <chs_canvas_base_for+0x4e>
 88010ae:	20c0      	movs	r0, #192	@ 0xc0
 88010b0:	4a31      	ldr	r2, [pc, #196]	@ (8801178 <chs_canvas_base_for+0x12c>)
 88010b2:	8813      	ldrh	r3, [r2, #0]
 88010b4:	07db      	lsls	r3, r3, #31
 88010b6:	17db      	asrs	r3, r3, #31
 88010b8:	4018      	ands	r0, r3
 88010ba:	8813      	ldrh	r3, [r2, #0]
 88010bc:	3301      	adds	r3, #1
 88010be:	041b      	lsls	r3, r3, #16
 88010c0:	0c1b      	lsrs	r3, r3, #16
 88010c2:	8013      	strh	r3, [r2, #0]
 88010c4:	2300      	movs	r3, #0
 88010c6:	4c20      	ldr	r4, [pc, #128]	@ (8801148 <chs_canvas_base_for+0xfc>)
 88010c8:	46a4      	mov	ip, r4
 88010ca:	009a      	lsls	r2, r3, #2
 88010cc:	4462      	add	r2, ip
 88010ce:	6814      	ldr	r4, [r2, #0]
 88010d0:	2c00      	cmp	r4, #0
 88010d2:	d023      	beq.n	880111c <chs_canvas_base_for+0xd0>
 88010d4:	3301      	adds	r3, #1
 88010d6:	2b06      	cmp	r3, #6
 88010d8:	d1f5      	bne.n	88010c6 <chs_canvas_base_for+0x7a>
 88010da:	4c1d      	ldr	r4, [pc, #116]	@ (8801150 <chs_canvas_base_for+0x104>)
 88010dc:	4b1a      	ldr	r3, [pc, #104]	@ (8801148 <chs_canvas_base_for+0xfc>)
 88010de:	6822      	ldr	r2, [r4, #0]
 88010e0:	4d1c      	ldr	r5, [pc, #112]	@ (8801154 <chs_canvas_base_for+0x108>)
 88010e2:	601a      	str	r2, [r3, #0]
 88010e4:	4a19      	ldr	r2, [pc, #100]	@ (880114c <chs_canvas_base_for+0x100>)
 88010e6:	882b      	ldrh	r3, [r5, #0]
 88010e8:	8013      	strh	r3, [r2, #0]
 88010ea:	4a1b      	ldr	r2, [pc, #108]	@ (8801158 <chs_canvas_base_for+0x10c>)
 88010ec:	6813      	ldr	r3, [r2, #0]
 88010ee:	6023      	str	r3, [r4, #0]
 88010f0:	4c1a      	ldr	r4, [pc, #104]	@ (880115c <chs_canvas_base_for+0x110>)
 88010f2:	8823      	ldrh	r3, [r4, #0]
 88010f4:	802b      	strh	r3, [r5, #0]
 88010f6:	4d1a      	ldr	r5, [pc, #104]	@ (8801160 <chs_canvas_base_for+0x114>)
 88010f8:	682b      	ldr	r3, [r5, #0]
 88010fa:	6013      	str	r3, [r2, #0]
 88010fc:	4a19      	ldr	r2, [pc, #100]	@ (8801164 <chs_canvas_base_for+0x118>)
 88010fe:	8813      	ldrh	r3, [r2, #0]
 8801100:	8023      	strh	r3, [r4, #0]
 8801102:	4c19      	ldr	r4, [pc, #100]	@ (8801168 <chs_canvas_base_for+0x11c>)
 8801104:	6823      	ldr	r3, [r4, #0]
 8801106:	602b      	str	r3, [r5, #0]
 8801108:	4d18      	ldr	r5, [pc, #96]	@ (880116c <chs_canvas_base_for+0x120>)
 880110a:	882b      	ldrh	r3, [r5, #0]
 880110c:	8013      	strh	r3, [r2, #0]
 880110e:	4a18      	ldr	r2, [pc, #96]	@ (8801170 <chs_canvas_base_for+0x124>)
 8801110:	6813      	ldr	r3, [r2, #0]
 8801112:	6023      	str	r3, [r4, #0]
 8801114:	4b17      	ldr	r3, [pc, #92]	@ (8801174 <chs_canvas_base_for+0x128>)
 8801116:	881c      	ldrh	r4, [r3, #0]
 8801118:	802c      	strh	r4, [r5, #0]
 880111a:	e003      	b.n	8801124 <chs_canvas_base_for+0xd8>
 880111c:	4c0b      	ldr	r4, [pc, #44]	@ (880114c <chs_canvas_base_for+0x100>)
 880111e:	46a4      	mov	ip, r4
 8801120:	005b      	lsls	r3, r3, #1
 8801122:	4463      	add	r3, ip
 8801124:	6011      	str	r1, [r2, #0]
 8801126:	8018      	strh	r0, [r3, #0]
 8801128:	bc30      	pop	{r4, r5}
 880112a:	bc02      	pop	{r1}
 880112c:	4708      	bx	r1
 880112e:	2000      	movs	r0, #0
 8801130:	e7fa      	b.n	8801128 <chs_canvas_base_for+0xdc>
 8801132:	4a06      	ldr	r2, [pc, #24]	@ (880114c <chs_canvas_base_for+0x100>)
 8801134:	4694      	mov	ip, r2
 8801136:	005b      	lsls	r3, r3, #1
 8801138:	4463      	add	r3, ip
 880113a:	8818      	ldrh	r0, [r3, #0]
 880113c:	e7f4      	b.n	8801128 <chs_canvas_base_for+0xdc>
 880113e:	46c0      	nop			@ (mov r8, r8)
 8801140:	0203ff82 	.word	0x0203ff82
 8801144:	000021c7 	.word	0x000021c7
 8801148:	0203ff50 	.word	0x0203ff50
 880114c:	0203ff68 	.word	0x0203ff68
 8801150:	0203ff54 	.word	0x0203ff54
 8801154:	0203ff6a 	.word	0x0203ff6a
 8801158:	0203ff58 	.word	0x0203ff58
 880115c:	0203ff6c 	.word	0x0203ff6c
 8801160:	0203ff5c 	.word	0x0203ff5c
 8801164:	0203ff6e 	.word	0x0203ff6e
 8801168:	0203ff60 	.word	0x0203ff60
 880116c:	0203ff70 	.word	0x0203ff70
 8801170:	0203ff64 	.word	0x0203ff64
 8801174:	0203ff72 	.word	0x0203ff72
 8801178:	0203ff80 	.word	0x0203ff80

0880117c <trace_glyph>:
 880117c:	b5f0      	push	{r4, r5, r6, r7, lr}
 880117e:	4657      	mov	r7, sl
 8801180:	4645      	mov	r5, r8
 8801182:	46de      	mov	lr, fp
 8801184:	464e      	mov	r6, r9
 8801186:	b5e0      	push	{r5, r6, r7, lr}
 8801188:	b08f      	sub	sp, #60	@ 0x3c
 880118a:	469b      	mov	fp, r3
 880118c:	ab18      	add	r3, sp, #96	@ 0x60
 880118e:	781b      	ldrb	r3, [r3, #0]
 8801190:	469a      	mov	sl, r3
 8801192:	ab19      	add	r3, sp, #100	@ 0x64
 8801194:	781b      	ldrb	r3, [r3, #0]
 8801196:	0004      	movs	r4, r0
 8801198:	0018      	movs	r0, r3
 880119a:	ab1a      	add	r3, sp, #104	@ 0x68
 880119c:	781d      	ldrb	r5, [r3, #0]
 880119e:	ab1b      	add	r3, sp, #108	@ 0x6c
 88011a0:	781b      	ldrb	r3, [r3, #0]
 88011a2:	4699      	mov	r9, r3
 88011a4:	ab1c      	add	r3, sp, #112	@ 0x70
 88011a6:	881b      	ldrh	r3, [r3, #0]
 88011a8:	9300      	str	r3, [sp, #0]
 88011aa:	ab1d      	add	r3, sp, #116	@ 0x74
 88011ac:	881b      	ldrh	r3, [r3, #0]
 88011ae:	9301      	str	r3, [sp, #4]
 88011b0:	ab1e      	add	r3, sp, #120	@ 0x78
 88011b2:	881b      	ldrh	r3, [r3, #0]
 88011b4:	9302      	str	r3, [sp, #8]
 88011b6:	ab1f      	add	r3, sp, #124	@ 0x7c
 88011b8:	781b      	ldrb	r3, [r3, #0]
 88011ba:	9303      	str	r3, [sp, #12]
 88011bc:	ab20      	add	r3, sp, #128	@ 0x80
 88011be:	781b      	ldrb	r3, [r3, #0]
 88011c0:	9304      	str	r3, [sp, #16]
 88011c2:	ab21      	add	r3, sp, #132	@ 0x84
 88011c4:	781b      	ldrb	r3, [r3, #0]
 88011c6:	9305      	str	r3, [sp, #20]
 88011c8:	ab22      	add	r3, sp, #136	@ 0x88
 88011ca:	781b      	ldrb	r3, [r3, #0]
 88011cc:	9306      	str	r3, [sp, #24]
 88011ce:	4b78      	ldr	r3, [pc, #480]	@ (88013b0 <trace_glyph+0x234>)
 88011d0:	4688      	mov	r8, r1
 88011d2:	0017      	movs	r7, r2
 88011d4:	6819      	ldr	r1, [r3, #0]
 88011d6:	4a77      	ldr	r2, [pc, #476]	@ (88013b4 <trace_glyph+0x238>)
 88011d8:	4291      	cmp	r1, r2
 88011da:	d00a      	beq.n	88011f2 <trace_glyph+0x76>
 88011dc:	2100      	movs	r1, #0
 88011de:	4684      	mov	ip, r0
 88011e0:	4a75      	ldr	r2, [pc, #468]	@ (88013b8 <trace_glyph+0x23c>)
 88011e2:	c302      	stmia	r3!, {r1}
 88011e4:	4293      	cmp	r3, r2
 88011e6:	d1fc      	bne.n	88011e2 <trace_glyph+0x66>
 88011e8:	4663      	mov	r3, ip
 88011ea:	4a72      	ldr	r2, [pc, #456]	@ (88013b4 <trace_glyph+0x238>)
 88011ec:	0018      	movs	r0, r3
 88011ee:	4b70      	ldr	r3, [pc, #448]	@ (88013b0 <trace_glyph+0x234>)
 88011f0:	601a      	str	r2, [r3, #0]
 88011f2:	2601      	movs	r6, #1
 88011f4:	4641      	mov	r1, r8
 88011f6:	4a71      	ldr	r2, [pc, #452]	@ (88013bc <trace_glyph+0x240>)
 88011f8:	6813      	ldr	r3, [r2, #0]
 88011fa:	4276      	negs	r6, r6
 88011fc:	3301      	adds	r3, #1
 88011fe:	6013      	str	r3, [r2, #0]
 8801200:	46a8      	mov	r8, r5
 8801202:	2220      	movs	r2, #32
 8801204:	2300      	movs	r3, #0
 8801206:	4684      	mov	ip, r0
 8801208:	0035      	movs	r5, r6
 880120a:	9107      	str	r1, [sp, #28]
 880120c:	e002      	b.n	8801214 <trace_glyph+0x98>
 880120e:	3220      	adds	r2, #32
 8801210:	2b18      	cmp	r3, #24
 8801212:	d010      	beq.n	8801236 <trace_glyph+0xba>
 8801214:	4966      	ldr	r1, [pc, #408]	@ (88013b0 <trace_glyph+0x234>)
 8801216:	1851      	adds	r1, r2, r1
 8801218:	6808      	ldr	r0, [r1, #0]
 880121a:	001e      	movs	r6, r3
 880121c:	3301      	adds	r3, #1
 880121e:	42a0      	cmp	r0, r4
 8801220:	d100      	bne.n	8801224 <trace_glyph+0xa8>
 8801222:	e07a      	b.n	880131a <trace_glyph+0x19e>
 8801224:	6809      	ldr	r1, [r1, #0]
 8801226:	2900      	cmp	r1, #0
 8801228:	d1f1      	bne.n	880120e <trace_glyph+0x92>
 880122a:	1c69      	adds	r1, r5, #1
 880122c:	d1ef      	bne.n	880120e <trace_glyph+0x92>
 880122e:	0035      	movs	r5, r6
 8801230:	3220      	adds	r2, #32
 8801232:	2b18      	cmp	r3, #24
 8801234:	d1ee      	bne.n	8801214 <trace_glyph+0x98>
 8801236:	4662      	mov	r2, ip
 8801238:	9b07      	ldr	r3, [sp, #28]
 880123a:	002e      	movs	r6, r5
 880123c:	0212      	lsls	r2, r2, #8
 880123e:	4645      	mov	r5, r8
 8801240:	4698      	mov	r8, r3
 8801242:	2e17      	cmp	r6, #23
 8801244:	d800      	bhi.n	8801248 <trace_glyph+0xcc>
 8801246:	e0a5      	b.n	8801394 <trace_glyph+0x218>
 8801248:	4649      	mov	r1, r9
 880124a:	042d      	lsls	r5, r5, #16
 880124c:	0609      	lsls	r1, r1, #24
 880124e:	430d      	orrs	r5, r1
 8801250:	4651      	mov	r1, sl
 8801252:	430d      	orrs	r5, r1
 8801254:	4315      	orrs	r5, r2
 8801256:	465a      	mov	r2, fp
 8801258:	9902      	ldr	r1, [sp, #8]
 880125a:	0712      	lsls	r2, r2, #28
 880125c:	0409      	lsls	r1, r1, #16
 880125e:	0c12      	lsrs	r2, r2, #16
 8801260:	430a      	orrs	r2, r1
 8801262:	433a      	orrs	r2, r7
 8801264:	920a      	str	r2, [sp, #40]	@ 0x28
 8801266:	9a01      	ldr	r2, [sp, #4]
 8801268:	9900      	ldr	r1, [sp, #0]
 880126a:	0412      	lsls	r2, r2, #16
 880126c:	430a      	orrs	r2, r1
 880126e:	920b      	str	r2, [sp, #44]	@ 0x2c
 8801270:	9906      	ldr	r1, [sp, #24]
 8801272:	9a05      	ldr	r2, [sp, #20]
 8801274:	0609      	lsls	r1, r1, #24
 8801276:	0412      	lsls	r2, r2, #16
 8801278:	430a      	orrs	r2, r1
 880127a:	9903      	ldr	r1, [sp, #12]
 880127c:	430a      	orrs	r2, r1
 880127e:	9904      	ldr	r1, [sp, #16]
 8801280:	0209      	lsls	r1, r1, #8
 8801282:	430a      	orrs	r2, r1
 8801284:	920c      	str	r2, [sp, #48]	@ 0x30
 8801286:	9408      	str	r4, [sp, #32]
 8801288:	4a4d      	ldr	r2, [pc, #308]	@ (88013c0 <trace_glyph+0x244>)
 880128a:	9509      	str	r5, [sp, #36]	@ 0x24
 880128c:	6811      	ldr	r1, [r2, #0]
 880128e:	ab08      	add	r3, sp, #32
 8801290:	2900      	cmp	r1, #0
 8801292:	d100      	bne.n	8801296 <trace_glyph+0x11a>
 8801294:	e073      	b.n	880137e <trace_glyph+0x202>
 8801296:	6811      	ldr	r1, [r2, #0]
 8801298:	22ff      	movs	r2, #255	@ 0xff
 880129a:	3901      	subs	r1, #1
 880129c:	400a      	ands	r2, r1
 880129e:	0091      	lsls	r1, r2, #2
 88012a0:	1889      	adds	r1, r1, r2
 88012a2:	22c8      	movs	r2, #200	@ 0xc8
 88012a4:	0092      	lsls	r2, r2, #2
 88012a6:	4694      	mov	ip, r2
 88012a8:	0089      	lsls	r1, r1, #2
 88012aa:	4461      	add	r1, ip
 88012ac:	4a44      	ldr	r2, [pc, #272]	@ (88013c0 <trace_glyph+0x244>)
 88012ae:	6810      	ldr	r0, [r2, #0]
 88012b0:	2800      	cmp	r0, #0
 88012b2:	d00f      	beq.n	88012d4 <trace_glyph+0x158>
 88012b4:	4843      	ldr	r0, [pc, #268]	@ (88013c4 <trace_glyph+0x248>)
 88012b6:	180d      	adds	r5, r1, r0
 88012b8:	4843      	ldr	r0, [pc, #268]	@ (88013c8 <trace_glyph+0x24c>)
 88012ba:	4684      	mov	ip, r0
 88012bc:	4a3c      	ldr	r2, [pc, #240]	@ (88013b0 <trace_glyph+0x234>)
 88012be:	188a      	adds	r2, r1, r2
 88012c0:	1a59      	subs	r1, r3, r1
 88012c2:	4461      	add	r1, ip
 88012c4:	6814      	ldr	r4, [r2, #0]
 88012c6:	5888      	ldr	r0, [r1, r2]
 88012c8:	4284      	cmp	r4, r0
 88012ca:	d16e      	bne.n	88013aa <trace_glyph+0x22e>
 88012cc:	3204      	adds	r2, #4
 88012ce:	42aa      	cmp	r2, r5
 88012d0:	d1f8      	bne.n	88012c4 <trace_glyph+0x148>
 88012d2:	4a3b      	ldr	r2, [pc, #236]	@ (88013c0 <trace_glyph+0x244>)
 88012d4:	6812      	ldr	r2, [r2, #0]
 88012d6:	2a00      	cmp	r2, #0
 88012d8:	d162      	bne.n	88013a0 <trace_glyph+0x224>
 88012da:	4a39      	ldr	r2, [pc, #228]	@ (88013c0 <trace_glyph+0x244>)
 88012dc:	6811      	ldr	r1, [r2, #0]
 88012de:	22ff      	movs	r2, #255	@ 0xff
 88012e0:	400a      	ands	r2, r1
 88012e2:	0091      	lsls	r1, r2, #2
 88012e4:	1889      	adds	r1, r1, r2
 88012e6:	4839      	ldr	r0, [pc, #228]	@ (88013cc <trace_glyph+0x250>)
 88012e8:	4a39      	ldr	r2, [pc, #228]	@ (88013d0 <trace_glyph+0x254>)
 88012ea:	0089      	lsls	r1, r1, #2
 88012ec:	1a5b      	subs	r3, r3, r1
 88012ee:	188a      	adds	r2, r1, r2
 88012f0:	1808      	adds	r0, r1, r0
 88012f2:	4938      	ldr	r1, [pc, #224]	@ (88013d4 <trace_glyph+0x258>)
 88012f4:	468c      	mov	ip, r1
 88012f6:	4463      	add	r3, ip
 88012f8:	5899      	ldr	r1, [r3, r2]
 88012fa:	c202      	stmia	r2!, {r1}
 88012fc:	4282      	cmp	r2, r0
 88012fe:	d1fb      	bne.n	88012f8 <trace_glyph+0x17c>
 8801300:	4a2f      	ldr	r2, [pc, #188]	@ (88013c0 <trace_glyph+0x244>)
 8801302:	6813      	ldr	r3, [r2, #0]
 8801304:	3301      	adds	r3, #1
 8801306:	6013      	str	r3, [r2, #0]
 8801308:	b00f      	add	sp, #60	@ 0x3c
 880130a:	bcf0      	pop	{r4, r5, r6, r7}
 880130c:	46bb      	mov	fp, r7
 880130e:	46b2      	mov	sl, r6
 8801310:	46a9      	mov	r9, r5
 8801312:	46a0      	mov	r8, r4
 8801314:	bcf0      	pop	{r4, r5, r6, r7}
 8801316:	bc01      	pop	{r0}
 8801318:	4700      	bx	r0
 880131a:	9807      	ldr	r0, [sp, #28]
 880131c:	4645      	mov	r5, r8
 880131e:	4680      	mov	r8, r0
 8801320:	482d      	ldr	r0, [pc, #180]	@ (88013d8 <trace_glyph+0x25c>)
 8801322:	4666      	mov	r6, ip
 8801324:	4684      	mov	ip, r0
 8801326:	4462      	add	r2, ip
 8801328:	6810      	ldr	r0, [r2, #0]
 880132a:	3001      	adds	r0, #1
 880132c:	6010      	str	r0, [r2, #0]
 880132e:	0232      	lsls	r2, r6, #8
 8801330:	6808      	ldr	r0, [r1, #0]
 8801332:	2800      	cmp	r0, #0
 8801334:	d000      	beq.n	8801338 <trace_glyph+0x1bc>
 8801336:	e787      	b.n	8801248 <trace_glyph+0xcc>
 8801338:	1e20      	subs	r0, r4, #0
 880133a:	d029      	beq.n	8801390 <trace_glyph+0x214>
 880133c:	6008      	str	r0, [r1, #0]
 880133e:	4640      	mov	r0, r8
 8801340:	491e      	ldr	r1, [pc, #120]	@ (88013bc <trace_glyph+0x240>)
 8801342:	015b      	lsls	r3, r3, #5
 8801344:	1859      	adds	r1, r3, r1
 8801346:	6008      	str	r0, [r1, #0]
 8801348:	491d      	ldr	r1, [pc, #116]	@ (88013c0 <trace_glyph+0x244>)
 880134a:	1859      	adds	r1, r3, r1
 880134c:	2800      	cmp	r0, #0
 880134e:	d119      	bne.n	8801384 <trace_glyph+0x208>
 8801350:	6008      	str	r0, [r1, #0]
 8801352:	4640      	mov	r0, r8
 8801354:	4921      	ldr	r1, [pc, #132]	@ (88013dc <trace_glyph+0x260>)
 8801356:	1859      	adds	r1, r3, r1
 8801358:	6008      	str	r0, [r1, #0]
 880135a:	2001      	movs	r0, #1
 880135c:	491e      	ldr	r1, [pc, #120]	@ (88013d8 <trace_glyph+0x25c>)
 880135e:	1859      	adds	r1, r3, r1
 8801360:	6008      	str	r0, [r1, #0]
 8801362:	4918      	ldr	r1, [pc, #96]	@ (88013c4 <trace_glyph+0x248>)
 8801364:	1859      	adds	r1, r3, r1
 8801366:	600f      	str	r7, [r1, #0]
 8801368:	491d      	ldr	r1, [pc, #116]	@ (88013e0 <trace_glyph+0x264>)
 880136a:	468c      	mov	ip, r1
 880136c:	4651      	mov	r1, sl
 880136e:	4463      	add	r3, ip
 8801370:	4311      	orrs	r1, r2
 8801372:	6019      	str	r1, [r3, #0]
 8801374:	4919      	ldr	r1, [pc, #100]	@ (88013dc <trace_glyph+0x260>)
 8801376:	680b      	ldr	r3, [r1, #0]
 8801378:	3301      	adds	r3, #1
 880137a:	600b      	str	r3, [r1, #0]
 880137c:	e764      	b.n	8801248 <trace_glyph+0xcc>
 880137e:	21c8      	movs	r1, #200	@ 0xc8
 8801380:	0089      	lsls	r1, r1, #2
 8801382:	e793      	b.n	88012ac <trace_glyph+0x130>
 8801384:	68c0      	ldr	r0, [r0, #12]
 8801386:	6008      	str	r0, [r1, #0]
 8801388:	4641      	mov	r1, r8
 880138a:	6909      	ldr	r1, [r1, #16]
 880138c:	4688      	mov	r8, r1
 880138e:	e7e0      	b.n	8801352 <trace_glyph+0x1d6>
 8801390:	2001      	movs	r0, #1
 8801392:	e7d3      	b.n	880133c <trace_glyph+0x1c0>
 8801394:	4806      	ldr	r0, [pc, #24]	@ (88013b0 <trace_glyph+0x234>)
 8801396:	4684      	mov	ip, r0
 8801398:	1c73      	adds	r3, r6, #1
 880139a:	0159      	lsls	r1, r3, #5
 880139c:	4461      	add	r1, ip
 880139e:	e7c7      	b.n	8801330 <trace_glyph+0x1b4>
 88013a0:	4a0d      	ldr	r2, [pc, #52]	@ (88013d8 <trace_glyph+0x25c>)
 88013a2:	6813      	ldr	r3, [r2, #0]
 88013a4:	3301      	adds	r3, #1
 88013a6:	6013      	str	r3, [r2, #0]
 88013a8:	e7ae      	b.n	8801308 <trace_glyph+0x18c>
 88013aa:	4a05      	ldr	r2, [pc, #20]	@ (88013c0 <trace_glyph+0x244>)
 88013ac:	6812      	ldr	r2, [r2, #0]
 88013ae:	e794      	b.n	88012da <trace_glyph+0x15e>
 88013b0:	0203c000 	.word	0x0203c000
 88013b4:	32584441 	.word	0x32584441
 88013b8:	0203e000 	.word	0x0203e000
 88013bc:	0203c004 	.word	0x0203c004
 88013c0:	0203c008 	.word	0x0203c008
 88013c4:	0203c014 	.word	0x0203c014
 88013c8:	fdfc4000 	.word	0xfdfc4000
 88013cc:	0203c334 	.word	0x0203c334
 88013d0:	0203c320 	.word	0x0203c320
 88013d4:	fdfc3ce0 	.word	0xfdfc3ce0
 88013d8:	0203c010 	.word	0x0203c010
 88013dc:	0203c00c 	.word	0x0203c00c
 88013e0:	0203c018 	.word	0x0203c018

088013e4 <chs_cell_from_1bpp>:
 88013e4:	b5f0      	push	{r4, r5, r6, r7, lr}
 88013e6:	4657      	mov	r7, sl
 88013e8:	4645      	mov	r5, r8
 88013ea:	46de      	mov	lr, fp
 88013ec:	464e      	mov	r6, r9
 88013ee:	b5e0      	push	{r5, r6, r7, lr}
 88013f0:	0005      	movs	r5, r0
 88013f2:	2000      	movs	r0, #0
 88013f4:	b095      	sub	sp, #84	@ 0x54
 88013f6:	469a      	mov	sl, r3
 88013f8:	ab0c      	add	r3, sp, #48	@ 0x30
 88013fa:	9306      	str	r3, [sp, #24]
 88013fc:	c301      	stmia	r3!, {r0}
 88013fe:	ac14      	add	r4, sp, #80	@ 0x50
 8801400:	429c      	cmp	r4, r3
 8801402:	d1fb      	bne.n	88013fc <chs_cell_from_1bpp+0x18>
 8801404:	2a00      	cmp	r2, #0
 8801406:	d057      	beq.n	88014b8 <chs_cell_from_1bpp+0xd4>
 8801408:	a80c      	add	r0, sp, #48	@ 0x30
 880140a:	4653      	mov	r3, sl
 880140c:	4683      	mov	fp, r0
 880140e:	4452      	add	r2, sl
 8801410:	4694      	mov	ip, r2
 8801412:	2207      	movs	r2, #7
 8801414:	005b      	lsls	r3, r3, #1
 8801416:	449b      	add	fp, r3
 8801418:	2300      	movs	r3, #0
 880141a:	4691      	mov	r9, r2
 880141c:	2601      	movs	r6, #1
 880141e:	4658      	mov	r0, fp
 8801420:	4664      	mov	r4, ip
 8801422:	46a8      	mov	r8, r5
 8801424:	9301      	str	r3, [sp, #4]
 8801426:	4652      	mov	r2, sl
 8801428:	2a0f      	cmp	r2, #15
 880142a:	d845      	bhi.n	88014b8 <chs_cell_from_1bpp+0xd4>
 880142c:	2700      	movs	r7, #0
 880142e:	2200      	movs	r2, #0
 8801430:	2900      	cmp	r1, #0
 8801432:	d035      	beq.n	88014a0 <chs_cell_from_1bpp+0xbc>
 8801434:	9d01      	ldr	r5, [sp, #4]
 8801436:	3d01      	subs	r5, #1
 8801438:	46a3      	mov	fp, r4
 880143a:	4694      	mov	ip, r2
 880143c:	000c      	movs	r4, r1
 880143e:	9002      	str	r0, [sp, #8]
 8801440:	4641      	mov	r1, r8
 8801442:	9500      	str	r5, [sp, #0]
 8801444:	46b8      	mov	r8, r7
 8801446:	e00c      	b.n	8801462 <chs_cell_from_1bpp+0x7e>
 8801448:	2800      	cmp	r0, #0
 880144a:	d007      	beq.n	880145c <chs_cell_from_1bpp+0x78>
 880144c:	0010      	movs	r0, r2
 880144e:	0035      	movs	r5, r6
 8801450:	3808      	subs	r0, #8
 8801452:	4085      	lsls	r5, r0
 8801454:	0028      	movs	r0, r5
 8801456:	4645      	mov	r5, r8
 8801458:	4305      	orrs	r5, r0
 880145a:	46a8      	mov	r8, r5
 880145c:	3201      	adds	r2, #1
 880145e:	4294      	cmp	r4, r2
 8801460:	d014      	beq.n	880148c <chs_cell_from_1bpp+0xa8>
 8801462:	464f      	mov	r7, r9
 8801464:	9d00      	ldr	r5, [sp, #0]
 8801466:	1898      	adds	r0, r3, r2
 8801468:	08c0      	lsrs	r0, r0, #3
 880146a:	5c08      	ldrb	r0, [r1, r0]
 880146c:	1aad      	subs	r5, r5, r2
 880146e:	403d      	ands	r5, r7
 8801470:	4128      	asrs	r0, r5
 8801472:	4030      	ands	r0, r6
 8801474:	2a07      	cmp	r2, #7
 8801476:	d8e7      	bhi.n	8801448 <chs_cell_from_1bpp+0x64>
 8801478:	2800      	cmp	r0, #0
 880147a:	d0ef      	beq.n	880145c <chs_cell_from_1bpp+0x78>
 880147c:	0030      	movs	r0, r6
 880147e:	4665      	mov	r5, ip
 8801480:	4090      	lsls	r0, r2
 8801482:	3201      	adds	r2, #1
 8801484:	4305      	orrs	r5, r0
 8801486:	46ac      	mov	ip, r5
 8801488:	4294      	cmp	r4, r2
 880148a:	d1ea      	bne.n	8801462 <chs_cell_from_1bpp+0x7e>
 880148c:	4647      	mov	r7, r8
 880148e:	4662      	mov	r2, ip
 8801490:	4688      	mov	r8, r1
 8801492:	0021      	movs	r1, r4
 8801494:	465c      	mov	r4, fp
 8801496:	0612      	lsls	r2, r2, #24
 8801498:	063f      	lsls	r7, r7, #24
 880149a:	9802      	ldr	r0, [sp, #8]
 880149c:	0e12      	lsrs	r2, r2, #24
 880149e:	0e3f      	lsrs	r7, r7, #24
 88014a0:	7002      	strb	r2, [r0, #0]
 88014a2:	2201      	movs	r2, #1
 88014a4:	4694      	mov	ip, r2
 88014a6:	9a01      	ldr	r2, [sp, #4]
 88014a8:	44e2      	add	sl, ip
 88014aa:	1a52      	subs	r2, r2, r1
 88014ac:	7047      	strb	r7, [r0, #1]
 88014ae:	9201      	str	r2, [sp, #4]
 88014b0:	3002      	adds	r0, #2
 88014b2:	185b      	adds	r3, r3, r1
 88014b4:	45a2      	cmp	sl, r4
 88014b6:	d1b6      	bne.n	8801426 <chs_cell_from_1bpp+0x42>
 88014b8:	2301      	movs	r3, #1
 88014ba:	425b      	negs	r3, r3
 88014bc:	469b      	mov	fp, r3
 88014be:	3310      	adds	r3, #16
 88014c0:	2600      	movs	r6, #0
 88014c2:	469a      	mov	sl, r3
 88014c4:	465d      	mov	r5, fp
 88014c6:	af0b      	add	r7, sp, #44	@ 0x2c
 88014c8:	0032      	movs	r2, r6
 88014ca:	1e53      	subs	r3, r2, #1
 88014cc:	419a      	sbcs	r2, r3
 88014ce:	4693      	mov	fp, r2
 88014d0:	2207      	movs	r2, #7
 88014d2:	2307      	movs	r3, #7
 88014d4:	4032      	ands	r2, r6
 88014d6:	0091      	lsls	r1, r2, #2
 88014d8:	469c      	mov	ip, r3
 88014da:	2200      	movs	r2, #0
 88014dc:	a80c      	add	r0, sp, #48	@ 0x30
 88014de:	4680      	mov	r8, r0
 88014e0:	0014      	movs	r4, r2
 88014e2:	45b4      	cmp	ip, r6
 88014e4:	419b      	sbcs	r3, r3
 88014e6:	3204      	adds	r2, #4
 88014e8:	4694      	mov	ip, r2
 88014ea:	006a      	lsls	r2, r5, #1
 88014ec:	4442      	add	r2, r8
 88014ee:	4688      	mov	r8, r1
 88014f0:	425b      	negs	r3, r3
 88014f2:	9205      	str	r2, [sp, #20]
 88014f4:	015b      	lsls	r3, r3, #5
 88014f6:	9a1e      	ldr	r2, [sp, #120]	@ 0x78
 88014f8:	4443      	add	r3, r8
 88014fa:	9108      	str	r1, [sp, #32]
 88014fc:	18d1      	adds	r1, r2, r3
 88014fe:	9109      	str	r1, [sp, #36]	@ 0x24
 8801500:	46a0      	mov	r8, r4
 8801502:	46d9      	mov	r9, fp
 8801504:	0029      	movs	r1, r5
 8801506:	9607      	str	r6, [sp, #28]
 8801508:	9404      	str	r4, [sp, #16]
 880150a:	2300      	movs	r3, #0
 880150c:	4645      	mov	r5, r8
 880150e:	9a04      	ldr	r2, [sp, #16]
 8801510:	603b      	str	r3, [r7, #0]
 8801512:	9b06      	ldr	r3, [sp, #24]
 8801514:	5c9e      	ldrb	r6, [r3, r2]
 8801516:	3d01      	subs	r5, #1
 8801518:	2300      	movs	r3, #0
 880151a:	2200      	movs	r2, #0
 880151c:	2000      	movs	r0, #0
 880151e:	2401      	movs	r4, #1
 8801520:	468b      	mov	fp, r1
 8801522:	9503      	str	r5, [sp, #12]
 8801524:	9600      	str	r6, [sp, #0]
 8801526:	e00a      	b.n	880153e <chs_cell_from_1bpp+0x15a>
 8801528:	4655      	mov	r5, sl
 880152a:	408d      	lsls	r5, r1
 880152c:	432b      	orrs	r3, r5
 880152e:	061b      	lsls	r3, r3, #24
 8801530:	0e1b      	lsrs	r3, r3, #24
 8801532:	3201      	adds	r2, #1
 8801534:	543b      	strb	r3, [r7, r0]
 8801536:	2a08      	cmp	r2, #8
 8801538:	d021      	beq.n	880157e <chs_cell_from_1bpp+0x19a>
 880153a:	0850      	lsrs	r0, r2, #1
 880153c:	5c3b      	ldrb	r3, [r7, r0]
 880153e:	4665      	mov	r5, ip
 8801540:	0091      	lsls	r1, r2, #2
 8801542:	4029      	ands	r1, r5
 8801544:	0025      	movs	r5, r4
 8801546:	4095      	lsls	r5, r2
 8801548:	9e00      	ldr	r6, [sp, #0]
 880154a:	4235      	tst	r5, r6
 880154c:	d1ec      	bne.n	8801528 <chs_cell_from_1bpp+0x144>
 880154e:	4645      	mov	r5, r8
 8801550:	18ad      	adds	r5, r5, r2
 8801552:	2d00      	cmp	r5, #0
 8801554:	d0ed      	beq.n	8801532 <chs_cell_from_1bpp+0x14e>
 8801556:	464d      	mov	r5, r9
 8801558:	2d00      	cmp	r5, #0
 880155a:	d0ea      	beq.n	8801532 <chs_cell_from_1bpp+0x14e>
 880155c:	9d03      	ldr	r5, [sp, #12]
 880155e:	18ad      	adds	r5, r5, r2
 8801560:	08ee      	lsrs	r6, r5, #3
 8801562:	9601      	str	r6, [sp, #4]
 8801564:	2607      	movs	r6, #7
 8801566:	4035      	ands	r5, r6
 8801568:	0026      	movs	r6, r4
 880156a:	40ae      	lsls	r6, r5
 880156c:	9d05      	ldr	r5, [sp, #20]
 880156e:	9602      	str	r6, [sp, #8]
 8801570:	9e01      	ldr	r6, [sp, #4]
 8801572:	5dad      	ldrb	r5, [r5, r6]
 8801574:	9e02      	ldr	r6, [sp, #8]
 8801576:	422e      	tst	r6, r5
 8801578:	d0db      	beq.n	8801532 <chs_cell_from_1bpp+0x14e>
 880157a:	250e      	movs	r5, #14
 880157c:	e7d5      	b.n	880152a <chs_cell_from_1bpp+0x146>
 880157e:	9d04      	ldr	r5, [sp, #16]
 8801580:	4659      	mov	r1, fp
 8801582:	783c      	ldrb	r4, [r7, #0]
 8801584:	7878      	ldrb	r0, [r7, #1]
 8801586:	78ba      	ldrb	r2, [r7, #2]
 8801588:	78fb      	ldrb	r3, [r7, #3]
 880158a:	2d00      	cmp	r5, #0
 880158c:	d021      	beq.n	88015d2 <chs_cell_from_1bpp+0x1ee>
 880158e:	9e07      	ldr	r6, [sp, #28]
 8801590:	000d      	movs	r5, r1
 8801592:	4698      	mov	r8, r3
 8801594:	2140      	movs	r1, #64	@ 0x40
 8801596:	2e07      	cmp	r6, #7
 8801598:	d900      	bls.n	880159c <chs_cell_from_1bpp+0x1b8>
 880159a:	3120      	adds	r1, #32
 880159c:	9b08      	ldr	r3, [sp, #32]
 880159e:	469c      	mov	ip, r3
 88015a0:	9b1e      	ldr	r3, [sp, #120]	@ 0x78
 88015a2:	4461      	add	r1, ip
 88015a4:	469c      	mov	ip, r3
 88015a6:	4643      	mov	r3, r8
 88015a8:	4461      	add	r1, ip
 88015aa:	70cb      	strb	r3, [r1, #3]
 88015ac:	9b06      	ldr	r3, [sp, #24]
 88015ae:	3601      	adds	r6, #1
 88015b0:	3302      	adds	r3, #2
 88015b2:	700c      	strb	r4, [r1, #0]
 88015b4:	7048      	strb	r0, [r1, #1]
 88015b6:	708a      	strb	r2, [r1, #2]
 88015b8:	9306      	str	r3, [sp, #24]
 88015ba:	3501      	adds	r5, #1
 88015bc:	2e10      	cmp	r6, #16
 88015be:	d183      	bne.n	88014c8 <chs_cell_from_1bpp+0xe4>
 88015c0:	b015      	add	sp, #84	@ 0x54
 88015c2:	bcf0      	pop	{r4, r5, r6, r7}
 88015c4:	46bb      	mov	fp, r7
 88015c6:	46b2      	mov	sl, r6
 88015c8:	46a9      	mov	r9, r5
 88015ca:	46a0      	mov	r8, r4
 88015cc:	bcf0      	pop	{r4, r5, r6, r7}
 88015ce:	bc01      	pop	{r0}
 88015d0:	4700      	bx	r0
 88015d2:	9d09      	ldr	r5, [sp, #36]	@ 0x24
 88015d4:	70eb      	strb	r3, [r5, #3]
 88015d6:	2308      	movs	r3, #8
 88015d8:	469b      	mov	fp, r3
 88015da:	3b07      	subs	r3, #7
 88015dc:	702c      	strb	r4, [r5, #0]
 88015de:	7068      	strb	r0, [r5, #1]
 88015e0:	70aa      	strb	r2, [r5, #2]
 88015e2:	9304      	str	r3, [sp, #16]
 88015e4:	44d8      	add	r8, fp
 88015e6:	e790      	b.n	880150a <chs_cell_from_1bpp+0x126>

088015e8 <slot_lookup_stream>:
 88015e8:	b5f0      	push	{r4, r5, r6, r7, lr}
 88015ea:	4645      	mov	r5, r8
 88015ec:	46de      	mov	lr, fp
 88015ee:	4657      	mov	r7, sl
 88015f0:	464e      	mov	r6, r9
 88015f2:	b5e0      	push	{r5, r6, r7, lr}
 88015f4:	0005      	movs	r5, r0
 88015f6:	b0af      	sub	sp, #188	@ 0xbc
 88015f8:	29ff      	cmp	r1, #255	@ 0xff
 88015fa:	d812      	bhi.n	8801622 <slot_lookup_stream+0x3a>
 88015fc:	48a2      	ldr	r0, [pc, #648]	@ (8801888 <slot_lookup_stream+0x2a0>)
 88015fe:	4ca3      	ldr	r4, [pc, #652]	@ (880188c <slot_lookup_stream+0x2a4>)
 8801600:	6806      	ldr	r6, [r0, #0]
 8801602:	2000      	movs	r0, #0
 8801604:	42a6      	cmp	r6, r4
 8801606:	d008      	beq.n	880161a <slot_lookup_stream+0x32>
 8801608:	b02f      	add	sp, #188	@ 0xbc
 880160a:	bcf0      	pop	{r4, r5, r6, r7}
 880160c:	46bb      	mov	fp, r7
 880160e:	46b2      	mov	sl, r6
 8801610:	46a9      	mov	r9, r5
 8801612:	46a0      	mov	r8, r4
 8801614:	bcf0      	pop	{r4, r5, r6, r7}
 8801616:	bc02      	pop	{r1}
 8801618:	4708      	bx	r1
 880161a:	4c9d      	ldr	r4, [pc, #628]	@ (8801890 <slot_lookup_stream+0x2a8>)
 880161c:	8824      	ldrh	r4, [r4, #0]
 880161e:	2c00      	cmp	r4, #0
 8801620:	d101      	bne.n	8801626 <slot_lookup_stream+0x3e>
 8801622:	2000      	movs	r0, #0
 8801624:	e7f0      	b.n	8801608 <slot_lookup_stream+0x20>
 8801626:	42a1      	cmp	r1, r4
 8801628:	4140      	adcs	r0, r0
 880162a:	4e9a      	ldr	r6, [pc, #616]	@ (8801894 <slot_lookup_stream+0x2ac>)
 880162c:	0600      	lsls	r0, r0, #24
 880162e:	8836      	ldrh	r6, [r6, #0]
 8801630:	2800      	cmp	r0, #0
 8801632:	d1f6      	bne.n	8801622 <slot_lookup_stream+0x3a>
 8801634:	2e00      	cmp	r6, #0
 8801636:	d0f4      	beq.n	8801622 <slot_lookup_stream+0x3a>
 8801638:	4c97      	ldr	r4, [pc, #604]	@ (8801898 <slot_lookup_stream+0x2b0>)
 880163a:	4f98      	ldr	r7, [pc, #608]	@ (880189c <slot_lookup_stream+0x2b4>)
 880163c:	0088      	lsls	r0, r1, #2
 880163e:	5904      	ldr	r4, [r0, r4]
 8801640:	59c0      	ldr	r0, [r0, r7]
 8801642:	4284      	cmp	r4, r0
 8801644:	d2ed      	bcs.n	8801622 <slot_lookup_stream+0x3a>
 8801646:	4f96      	ldr	r7, [pc, #600]	@ (88018a0 <slot_lookup_stream+0x2b8>)
 8801648:	970d      	str	r7, [sp, #52]	@ 0x34
 880164a:	1c37      	adds	r7, r6, #0
 880164c:	2e20      	cmp	r6, #32
 880164e:	d900      	bls.n	8801652 <slot_lookup_stream+0x6a>
 8801650:	2720      	movs	r7, #32
 8801652:	043f      	lsls	r7, r7, #16
 8801654:	0c3e      	lsrs	r6, r7, #16
 8801656:	46b1      	mov	r9, r6
 8801658:	ae05      	add	r6, sp, #20
 880165a:	46b4      	mov	ip, r6
 880165c:	0609      	lsls	r1, r1, #24
 880165e:	ae0e      	add	r6, sp, #56	@ 0x38
 8801660:	46b0      	mov	r8, r6
 8801662:	0e0e      	lsrs	r6, r1, #24
 8801664:	498e      	ldr	r1, [pc, #568]	@ (88018a0 <slot_lookup_stream+0x2b8>)
 8801666:	468b      	mov	fp, r1
 8801668:	1e59      	subs	r1, r3, #1
 880166a:	468a      	mov	sl, r1
 880166c:	4452      	add	r2, sl
 880166e:	4692      	mov	sl, r2
 8801670:	2700      	movs	r7, #0
 8801672:	4662      	mov	r2, ip
 8801674:	4659      	mov	r1, fp
 8801676:	4684      	mov	ip, r0
 8801678:	4648      	mov	r0, r9
 880167a:	4699      	mov	r9, r3
 880167c:	4643      	mov	r3, r8
 880167e:	46a0      	mov	r8, r4
 8801680:	4654      	mov	r4, sl
 8801682:	e000      	b.n	8801686 <slot_lookup_stream+0x9e>
 8801684:	5de6      	ldrb	r6, [r4, r7]
 8801686:	2eff      	cmp	r6, #255	@ 0xff
 8801688:	d100      	bne.n	880168c <slot_lookup_stream+0xa4>
 880168a:	e0a3      	b.n	88017d4 <slot_lookup_stream+0x1ec>
 880168c:	4071      	eors	r1, r6
 880168e:	7016      	strb	r6, [r2, #0]
 8801690:	040e      	lsls	r6, r1, #16
 8801692:	1876      	adds	r6, r6, r1
 8801694:	0076      	lsls	r6, r6, #1
 8801696:	1876      	adds	r6, r6, r1
 8801698:	00f6      	lsls	r6, r6, #3
 880169a:	1876      	adds	r6, r6, r1
 880169c:	00f6      	lsls	r6, r6, #3
 880169e:	1876      	adds	r6, r6, r1
 88016a0:	0076      	lsls	r6, r6, #1
 88016a2:	1871      	adds	r1, r6, r1
 88016a4:	3701      	adds	r7, #1
 88016a6:	c302      	stmia	r3!, {r1}
 88016a8:	3201      	adds	r2, #1
 88016aa:	42b8      	cmp	r0, r7
 88016ac:	d8ea      	bhi.n	8801684 <slot_lookup_stream+0x9c>
 88016ae:	4660      	mov	r0, ip
 88016b0:	4644      	mov	r4, r8
 88016b2:	464b      	mov	r3, r9
 88016b4:	2200      	movs	r2, #0
 88016b6:	9202      	str	r2, [sp, #8]
 88016b8:	9201      	str	r2, [sp, #4]
 88016ba:	9200      	str	r2, [sp, #0]
 88016bc:	4a79      	ldr	r2, [pc, #484]	@ (88018a4 <slot_lookup_stream+0x2bc>)
 88016be:	4691      	mov	r9, r2
 88016c0:	4a73      	ldr	r2, [pc, #460]	@ (8801890 <slot_lookup_stream+0x2a8>)
 88016c2:	46bc      	mov	ip, r7
 88016c4:	4693      	mov	fp, r2
 88016c6:	46a8      	mov	r8, r5
 88016c8:	4e6f      	ldr	r6, [pc, #444]	@ (8801888 <slot_lookup_stream+0x2a0>)
 88016ca:	9303      	str	r3, [sp, #12]
 88016cc:	464b      	mov	r3, r9
 88016ce:	465a      	mov	r2, fp
 88016d0:	5ce3      	ldrb	r3, [r4, r3]
 88016d2:	5ca2      	ldrb	r2, [r4, r2]
 88016d4:	021b      	lsls	r3, r3, #8
 88016d6:	431a      	orrs	r2, r3
 88016d8:	0411      	lsls	r1, r2, #16
 88016da:	1da3      	adds	r3, r4, #6
 88016dc:	1409      	asrs	r1, r1, #16
 88016de:	18d3      	adds	r3, r2, r3
 88016e0:	2a00      	cmp	r2, #0
 88016e2:	d020      	beq.n	8801726 <slot_lookup_stream+0x13e>
 88016e4:	4594      	cmp	ip, r2
 88016e6:	d31e      	bcc.n	8801726 <slot_lookup_stream+0x13e>
 88016e8:	4d67      	ldr	r5, [pc, #412]	@ (8801888 <slot_lookup_stream+0x2a0>)
 88016ea:	46aa      	mov	sl, r5
 88016ec:	44a2      	add	sl, r4
 88016ee:	4655      	mov	r5, sl
 88016f0:	786d      	ldrb	r5, [r5, #1]
 88016f2:	5da7      	ldrb	r7, [r4, r6]
 88016f4:	022d      	lsls	r5, r5, #8
 88016f6:	433d      	orrs	r5, r7
 88016f8:	4657      	mov	r7, sl
 88016fa:	78bf      	ldrb	r7, [r7, #2]
 88016fc:	043f      	lsls	r7, r7, #16
 88016fe:	433d      	orrs	r5, r7
 8801700:	4657      	mov	r7, sl
 8801702:	0089      	lsls	r1, r1, #2
 8801704:	468a      	mov	sl, r1
 8801706:	2124      	movs	r1, #36	@ 0x24
 8801708:	78ff      	ldrb	r7, [r7, #3]
 880170a:	063f      	lsls	r7, r7, #24
 880170c:	432f      	orrs	r7, r5
 880170e:	ad04      	add	r5, sp, #16
 8801710:	186d      	adds	r5, r5, r1
 8801712:	4651      	mov	r1, sl
 8801714:	5869      	ldr	r1, [r5, r1]
 8801716:	428f      	cmp	r7, r1
 8801718:	d105      	bne.n	8801726 <slot_lookup_stream+0x13e>
 880171a:	e06e      	b.n	88017fa <slot_lookup_stream+0x212>
 880171c:	5d9a      	ldrb	r2, [r3, r6]
 880171e:	001c      	movs	r4, r3
 8801720:	3301      	adds	r3, #1
 8801722:	2aff      	cmp	r2, #255	@ 0xff
 8801724:	d002      	beq.n	880172c <slot_lookup_stream+0x144>
 8801726:	4298      	cmp	r0, r3
 8801728:	d8f8      	bhi.n	880171c <slot_lookup_stream+0x134>
 880172a:	001c      	movs	r4, r3
 880172c:	3401      	adds	r4, #1
 880172e:	42a0      	cmp	r0, r4
 8801730:	d8cc      	bhi.n	88016cc <slot_lookup_stream+0xe4>
 8801732:	9b00      	ldr	r3, [sp, #0]
 8801734:	4645      	mov	r5, r8
 8801736:	2b00      	cmp	r3, #0
 8801738:	d100      	bne.n	880173c <slot_lookup_stream+0x154>
 880173a:	e772      	b.n	8801622 <slot_lookup_stream+0x3a>
 880173c:	9a01      	ldr	r2, [sp, #4]
 880173e:	7811      	ldrb	r1, [r2, #0]
 8801740:	2400      	movs	r4, #0
 8801742:	29ff      	cmp	r1, #255	@ 0xff
 8801744:	d100      	bne.n	8801748 <slot_lookup_stream+0x160>
 8801746:	e084      	b.n	8801852 <slot_lookup_stream+0x26a>
 8801748:	4b57      	ldr	r3, [pc, #348]	@ (88018a8 <slot_lookup_stream+0x2c0>)
 880174a:	469b      	mov	fp, r3
 880174c:	4b57      	ldr	r3, [pc, #348]	@ (88018ac <slot_lookup_stream+0x2c4>)
 880174e:	46a9      	mov	r9, r5
 8801750:	469a      	mov	sl, r3
 8801752:	4690      	mov	r8, r2
 8801754:	0015      	movs	r5, r2
 8801756:	e00f      	b.n	8801778 <slot_lookup_stream+0x190>
 8801758:	29fd      	cmp	r1, #253	@ 0xfd
 880175a:	d043      	beq.n	88017e4 <slot_lookup_stream+0x1fc>
 880175c:	0433      	lsls	r3, r6, #16
 880175e:	002a      	movs	r2, r5
 8801760:	4648      	mov	r0, r9
 8801762:	0c1b      	lsrs	r3, r3, #16
 8801764:	f7ff ff40 	bl	88015e8 <slot_lookup_stream>
 8801768:	2800      	cmp	r0, #0
 880176a:	d06b      	beq.n	8801844 <slot_lookup_stream+0x25c>
 880176c:	46b8      	mov	r8, r7
 880176e:	0034      	movs	r4, r6
 8801770:	4643      	mov	r3, r8
 8801772:	7819      	ldrb	r1, [r3, #0]
 8801774:	29ff      	cmp	r1, #255	@ 0xff
 8801776:	d06b      	beq.n	8801850 <slot_lookup_stream+0x268>
 8801778:	1c66      	adds	r6, r4, #1
 880177a:	19af      	adds	r7, r5, r6
 880177c:	29f9      	cmp	r1, #249	@ 0xf9
 880177e:	d1eb      	bne.n	8801758 <slot_lookup_stream+0x170>
 8801780:	783b      	ldrb	r3, [r7, #0]
 8801782:	2b00      	cmp	r3, #0
 8801784:	d1ea      	bne.n	880175c <slot_lookup_stream+0x174>
 8801786:	271d      	movs	r7, #29
 8801788:	192a      	adds	r2, r5, r4
 880178a:	7893      	ldrb	r3, [r2, #2]
 880178c:	1e5e      	subs	r6, r3, #1
 880178e:	0630      	lsls	r0, r6, #24
 8801790:	78d2      	ldrb	r2, [r2, #3]
 8801792:	0e00      	lsrs	r0, r0, #24
 8801794:	4287      	cmp	r7, r0
 8801796:	d319      	bcc.n	88017cc <slot_lookup_stream+0x1e4>
 8801798:	4291      	cmp	r1, r2
 880179a:	d317      	bcc.n	88017cc <slot_lookup_stream+0x1e4>
 880179c:	2b06      	cmp	r3, #6
 880179e:	d015      	beq.n	88017cc <slot_lookup_stream+0x1e4>
 88017a0:	2b1b      	cmp	r3, #27
 88017a2:	d013      	beq.n	88017cc <slot_lookup_stream+0x1e4>
 88017a4:	2b05      	cmp	r3, #5
 88017a6:	d85c      	bhi.n	8801862 <slot_lookup_stream+0x27a>
 88017a8:	0236      	lsls	r6, r6, #8
 88017aa:	4316      	orrs	r6, r2
 88017ac:	0431      	lsls	r1, r6, #16
 88017ae:	0c09      	lsrs	r1, r1, #16
 88017b0:	464b      	mov	r3, r9
 88017b2:	2207      	movs	r2, #7
 88017b4:	7a9b      	ldrb	r3, [r3, #10]
 88017b6:	401a      	ands	r2, r3
 88017b8:	3a02      	subs	r2, #2
 88017ba:	4253      	negs	r3, r2
 88017bc:	415a      	adcs	r2, r3
 88017be:	2301      	movs	r3, #1
 88017c0:	4252      	negs	r2, r2
 88017c2:	439a      	bics	r2, r3
 88017c4:	4648      	mov	r0, r9
 88017c6:	320c      	adds	r2, #12
 88017c8:	f7ff f96c 	bl	8800aa4 <chs_print>
 88017cc:	3404      	adds	r4, #4
 88017ce:	192b      	adds	r3, r5, r4
 88017d0:	4698      	mov	r8, r3
 88017d2:	e7cd      	b.n	8801770 <slot_lookup_stream+0x188>
 88017d4:	4660      	mov	r0, ip
 88017d6:	4644      	mov	r4, r8
 88017d8:	464b      	mov	r3, r9
 88017da:	2f00      	cmp	r7, #0
 88017dc:	d000      	beq.n	88017e0 <slot_lookup_stream+0x1f8>
 88017de:	e769      	b.n	88016b4 <slot_lookup_stream+0xcc>
 88017e0:	2000      	movs	r0, #0
 88017e2:	e711      	b.n	8801608 <slot_lookup_stream+0x20>
 88017e4:	7838      	ldrb	r0, [r7, #0]
 88017e6:	f000 fa4a 	bl	8801c7e <GetStringWidth+0xc2>
 88017ea:	3402      	adds	r4, #2
 88017ec:	0001      	movs	r1, r0
 88017ee:	4648      	mov	r0, r9
 88017f0:	f000 fa44 	bl	8801c7c <GetStringWidth+0xc0>
 88017f4:	192b      	adds	r3, r5, r4
 88017f6:	4698      	mov	r8, r3
 88017f8:	e7ba      	b.n	8801770 <slot_lookup_stream+0x188>
 88017fa:	4926      	ldr	r1, [pc, #152]	@ (8801894 <slot_lookup_stream+0x2ac>)
 88017fc:	4f2c      	ldr	r7, [pc, #176]	@ (88018b0 <slot_lookup_stream+0x2c8>)
 88017fe:	1861      	adds	r1, r4, r1
 8801800:	1b3f      	subs	r7, r7, r4
 8801802:	ac05      	add	r4, sp, #20
 8801804:	46a2      	mov	sl, r4
 8801806:	44ba      	add	sl, r7
 8801808:	4654      	mov	r4, sl
 880180a:	469a      	mov	sl, r3
 880180c:	003b      	movs	r3, r7
 880180e:	0027      	movs	r7, r4
 8801810:	780d      	ldrb	r5, [r1, #0]
 8801812:	5c7c      	ldrb	r4, [r7, r1]
 8801814:	42a5      	cmp	r5, r4
 8801816:	d122      	bne.n	880185e <slot_lookup_stream+0x276>
 8801818:	3101      	adds	r1, #1
 880181a:	185c      	adds	r4, r3, r1
 880181c:	4294      	cmp	r4, r2
 880181e:	d3f7      	bcc.n	8801810 <slot_lookup_stream+0x228>
 8801820:	9900      	ldr	r1, [sp, #0]
 8801822:	4653      	mov	r3, sl
 8801824:	428a      	cmp	r2, r1
 8801826:	d200      	bcs.n	880182a <slot_lookup_stream+0x242>
 8801828:	e77d      	b.n	8801726 <slot_lookup_stream+0x13e>
 880182a:	4917      	ldr	r1, [pc, #92]	@ (8801888 <slot_lookup_stream+0x2a0>)
 880182c:	468a      	mov	sl, r1
 880182e:	449a      	add	sl, r3
 8801830:	4651      	mov	r1, sl
 8801832:	9101      	str	r1, [sp, #4]
 8801834:	9903      	ldr	r1, [sp, #12]
 8801836:	3901      	subs	r1, #1
 8801838:	1851      	adds	r1, r2, r1
 880183a:	0409      	lsls	r1, r1, #16
 880183c:	0c09      	lsrs	r1, r1, #16
 880183e:	9102      	str	r1, [sp, #8]
 8801840:	9200      	str	r2, [sp, #0]
 8801842:	e770      	b.n	8801726 <slot_lookup_stream+0x13e>
 8801844:	4643      	mov	r3, r8
 8801846:	4648      	mov	r0, r9
 8801848:	7819      	ldrb	r1, [r3, #0]
 880184a:	f7ff f9d1 	bl	8800bf0 <DrawGlyph>
 880184e:	e78d      	b.n	880176c <slot_lookup_stream+0x184>
 8801850:	464d      	mov	r5, r9
 8801852:	9b02      	ldr	r3, [sp, #8]
 8801854:	752b      	strb	r3, [r5, #20]
 8801856:	0a1b      	lsrs	r3, r3, #8
 8801858:	2001      	movs	r0, #1
 880185a:	756b      	strb	r3, [r5, #21]
 880185c:	e6d4      	b.n	8801608 <slot_lookup_stream+0x20>
 880185e:	4653      	mov	r3, sl
 8801860:	e761      	b.n	8801726 <slot_lookup_stream+0x13e>
 8801862:	2b1a      	cmp	r3, #26
 8801864:	d809      	bhi.n	880187a <slot_lookup_stream+0x292>
 8801866:	3b02      	subs	r3, #2
 8801868:	021b      	lsls	r3, r3, #8
 880186a:	431a      	orrs	r2, r3
 880186c:	23e0      	movs	r3, #224	@ 0xe0
 880186e:	0411      	lsls	r1, r2, #16
 8801870:	0c09      	lsrs	r1, r1, #16
 8801872:	015b      	lsls	r3, r3, #5
 8801874:	4299      	cmp	r1, r3
 8801876:	d2a9      	bcs.n	88017cc <slot_lookup_stream+0x1e4>
 8801878:	e79a      	b.n	88017b0 <slot_lookup_stream+0x1c8>
 880187a:	3b03      	subs	r3, #3
 880187c:	021b      	lsls	r3, r3, #8
 880187e:	4313      	orrs	r3, r2
 8801880:	0419      	lsls	r1, r3, #16
 8801882:	0c09      	lsrs	r1, r1, #16
 8801884:	e794      	b.n	88017b0 <slot_lookup_stream+0x1c8>
 8801886:	46c0      	nop			@ (mov r8, r8)
 8801888:	09ea0000 	.word	0x09ea0000
 880188c:	32544c53 	.word	0x32544c53
 8801890:	09ea0004 	.word	0x09ea0004
 8801894:	09ea0006 	.word	0x09ea0006
 8801898:	09ea0008 	.word	0x09ea0008
 880189c:	09ea000c 	.word	0x09ea000c
 88018a0:	811c9dc5 	.word	0x811c9dc5
 88018a4:	09ea0005 	.word	0x09ea0005
 88018a8:	080046d5 	.word	0x080046d5
 88018ac:	08002db5 	.word	0x08002db5
 88018b0:	f615fffa 	.word	0xf615fffa

088018b4 <GetGlyph>:
 88018b4:	b510      	push	{r4, lr}
 88018b6:	b082      	sub	sp, #8
 88018b8:	001c      	movs	r4, r3
 88018ba:	466b      	mov	r3, sp
 88018bc:	7c1b      	ldrb	r3, [r3, #16]
 88018be:	2900      	cmp	r1, #0
 88018c0:	d00a      	beq.n	88018d8 <GetGlyph+0x24>
 88018c2:	2b01      	cmp	r3, #1
 88018c4:	d023      	beq.n	880190e <GetGlyph+0x5a>
 88018c6:	2b02      	cmp	r3, #2
 88018c8:	d02e      	beq.n	8801928 <GetGlyph+0x74>
 88018ca:	2000      	movs	r0, #0
 88018cc:	2b03      	cmp	r3, #3
 88018ce:	d00d      	beq.n	88018ec <GetGlyph+0x38>
 88018d0:	b002      	add	sp, #8
 88018d2:	bc10      	pop	{r4}
 88018d4:	bc02      	pop	{r1}
 88018d6:	4708      	bx	r1
 88018d8:	0010      	movs	r0, r2
 88018da:	3080      	adds	r0, #128	@ 0x80
 88018dc:	7011      	strb	r1, [r2, #0]
 88018de:	3201      	adds	r2, #1
 88018e0:	4282      	cmp	r2, r0
 88018e2:	d1fb      	bne.n	88018dc <GetGlyph+0x28>
 88018e4:	2308      	movs	r3, #8
 88018e6:	2001      	movs	r0, #1
 88018e8:	7023      	strb	r3, [r4, #0]
 88018ea:	e7f1      	b.n	88018d0 <GetGlyph+0x1c>
 88018ec:	04c9      	lsls	r1, r1, #19
 88018ee:	0ccb      	lsrs	r3, r1, #19
 88018f0:	0c48      	lsrs	r0, r1, #17
 88018f2:	18c0      	adds	r0, r0, r3
 88018f4:	0040      	lsls	r0, r0, #1
 88018f6:	18c0      	adds	r0, r0, r3
 88018f8:	2396      	movs	r3, #150	@ 0x96
 88018fa:	051b      	lsls	r3, r3, #20
 88018fc:	469c      	mov	ip, r3
 88018fe:	9200      	str	r2, [sp, #0]
 8801900:	2305      	movs	r3, #5
 8801902:	2209      	movs	r2, #9
 8801904:	2109      	movs	r1, #9
 8801906:	4460      	add	r0, ip
 8801908:	f7ff fd6c 	bl	88013e4 <chs_cell_from_1bpp>
 880190c:	e7ea      	b.n	88018e4 <GetGlyph+0x30>
 880190e:	2395      	movs	r3, #149	@ 0x95
 8801910:	051b      	lsls	r3, r3, #20
 8801912:	469c      	mov	ip, r3
 8801914:	04c8      	lsls	r0, r1, #19
 8801916:	0bc0      	lsrs	r0, r0, #15
 8801918:	9200      	str	r2, [sp, #0]
 880191a:	2302      	movs	r3, #2
 880191c:	220b      	movs	r2, #11
 880191e:	210b      	movs	r1, #11
 8801920:	4460      	add	r0, ip
 8801922:	f7ff fd5f 	bl	88013e4 <chs_cell_from_1bpp>
 8801926:	e7dd      	b.n	88018e4 <GetGlyph+0x30>
 8801928:	04c9      	lsls	r1, r1, #19
 880192a:	0ccb      	lsrs	r3, r1, #19
 880192c:	0c88      	lsrs	r0, r1, #18
 880192e:	18c0      	adds	r0, r0, r3
 8801930:	0080      	lsls	r0, r0, #2
 8801932:	18c0      	adds	r0, r0, r3
 8801934:	2397      	movs	r3, #151	@ 0x97
 8801936:	051b      	lsls	r3, r3, #20
 8801938:	469c      	mov	ip, r3
 880193a:	9200      	str	r2, [sp, #0]
 880193c:	2302      	movs	r3, #2
 880193e:	220b      	movs	r2, #11
 8801940:	2109      	movs	r1, #9
 8801942:	4460      	add	r0, ip
 8801944:	f7ff fd4e 	bl	88013e4 <chs_cell_from_1bpp>
 8801948:	e7cc      	b.n	88018e4 <GetGlyph+0x30>
 880194a:	46c0      	nop			@ (mov r8, r8)

0880194c <TranslateHandleChar>:
 880194c:	b5f0      	push	{r4, r5, r6, r7, lr}
 880194e:	4645      	mov	r5, r8
 8801950:	46de      	mov	lr, fp
 8801952:	4657      	mov	r7, sl
 8801954:	464e      	mov	r6, r9
 8801956:	b5e0      	push	{r5, r6, r7, lr}
 8801958:	7d45      	ldrb	r5, [r0, #21]
 880195a:	7d03      	ldrb	r3, [r0, #20]
 880195c:	7c42      	ldrb	r2, [r0, #17]
 880195e:	022d      	lsls	r5, r5, #8
 8801960:	431d      	orrs	r5, r3
 8801962:	7c03      	ldrb	r3, [r0, #16]
 8801964:	0212      	lsls	r2, r2, #8
 8801966:	431a      	orrs	r2, r3
 8801968:	7c83      	ldrb	r3, [r0, #18]
 880196a:	041b      	lsls	r3, r3, #16
 880196c:	4313      	orrs	r3, r2
 880196e:	7cc2      	ldrb	r2, [r0, #19]
 8801970:	0612      	lsls	r2, r2, #24
 8801972:	0004      	movs	r4, r0
 8801974:	b083      	sub	sp, #12
 8801976:	431a      	orrs	r2, r3
 8801978:	29f9      	cmp	r1, #249	@ 0xf9
 880197a:	d000      	beq.n	880197e <TranslateHandleChar+0x32>
 880197c:	e080      	b.n	8801a80 <TranslateHandleChar+0x134>
 880197e:	5d53      	ldrb	r3, [r2, r5]
 8801980:	1950      	adds	r0, r2, r5
 8801982:	2b00      	cmp	r3, #0
 8801984:	d131      	bne.n	88019ea <TranslateHandleChar+0x9e>
 8801986:	7843      	ldrb	r3, [r0, #1]
 8801988:	3503      	adds	r5, #3
 880198a:	1e5f      	subs	r7, r3, #1
 880198c:	042e      	lsls	r6, r5, #16
 880198e:	063a      	lsls	r2, r7, #24
 8801990:	062d      	lsls	r5, r5, #24
 8801992:	7880      	ldrb	r0, [r0, #2]
 8801994:	0e2d      	lsrs	r5, r5, #24
 8801996:	0e36      	lsrs	r6, r6, #24
 8801998:	0e12      	lsrs	r2, r2, #24
 880199a:	2a1d      	cmp	r2, #29
 880199c:	d86d      	bhi.n	8801a7a <TranslateHandleChar+0x12e>
 880199e:	4281      	cmp	r1, r0
 88019a0:	d36b      	bcc.n	8801a7a <TranslateHandleChar+0x12e>
 88019a2:	2b06      	cmp	r3, #6
 88019a4:	d069      	beq.n	8801a7a <TranslateHandleChar+0x12e>
 88019a6:	2b1b      	cmp	r3, #27
 88019a8:	d067      	beq.n	8801a7a <TranslateHandleChar+0x12e>
 88019aa:	7525      	strb	r5, [r4, #20]
 88019ac:	7566      	strb	r6, [r4, #21]
 88019ae:	2b05      	cmp	r3, #5
 88019b0:	d900      	bls.n	88019b4 <TranslateHandleChar+0x68>
 88019b2:	e081      	b.n	8801ab8 <TranslateHandleChar+0x16c>
 88019b4:	023f      	lsls	r7, r7, #8
 88019b6:	4338      	orrs	r0, r7
 88019b8:	0400      	lsls	r0, r0, #16
 88019ba:	0c01      	lsrs	r1, r0, #16
 88019bc:	2207      	movs	r2, #7
 88019be:	7aa3      	ldrb	r3, [r4, #10]
 88019c0:	401a      	ands	r2, r3
 88019c2:	3a02      	subs	r2, #2
 88019c4:	4253      	negs	r3, r2
 88019c6:	415a      	adcs	r2, r3
 88019c8:	2301      	movs	r3, #1
 88019ca:	4252      	negs	r2, r2
 88019cc:	439a      	bics	r2, r3
 88019ce:	0020      	movs	r0, r4
 88019d0:	320c      	adds	r2, #12
 88019d2:	f7ff f867 	bl	8800aa4 <chs_print>
 88019d6:	2001      	movs	r0, #1
 88019d8:	b003      	add	sp, #12
 88019da:	bcf0      	pop	{r4, r5, r6, r7}
 88019dc:	46bb      	mov	fp, r7
 88019de:	46b2      	mov	sl, r6
 88019e0:	46a9      	mov	r9, r5
 88019e2:	46a0      	mov	r8, r4
 88019e4:	bcf0      	pop	{r4, r5, r6, r7}
 88019e6:	bc02      	pop	{r1}
 88019e8:	4708      	bx	r1
 88019ea:	7883      	ldrb	r3, [r0, #2]
 88019ec:	7842      	ldrb	r2, [r0, #1]
 88019ee:	021b      	lsls	r3, r3, #8
 88019f0:	431a      	orrs	r2, r3
 88019f2:	0212      	lsls	r2, r2, #8
 88019f4:	0a1b      	lsrs	r3, r3, #8
 88019f6:	4313      	orrs	r3, r2
 88019f8:	4a6c      	ldr	r2, [pc, #432]	@ (8801bac <TranslateHandleChar+0x260>)
 88019fa:	4693      	mov	fp, r2
 88019fc:	041b      	lsls	r3, r3, #16
 88019fe:	0b9b      	lsrs	r3, r3, #14
 8801a00:	449b      	add	fp, r3
 8801a02:	465b      	mov	r3, fp
 8801a04:	2280      	movs	r2, #128	@ 0x80
 8801a06:	681b      	ldr	r3, [r3, #0]
 8801a08:	0452      	lsls	r2, r2, #17
 8801a0a:	4293      	cmp	r3, r2
 8801a0c:	d2e3      	bcs.n	88019d6 <TranslateHandleChar+0x8a>
 8801a0e:	4a68      	ldr	r2, [pc, #416]	@ (8801bb0 <TranslateHandleChar+0x264>)
 8801a10:	4692      	mov	sl, r2
 8801a12:	449a      	add	sl, r3
 8801a14:	4653      	mov	r3, sl
 8801a16:	7819      	ldrb	r1, [r3, #0]
 8801a18:	29ff      	cmp	r1, #255	@ 0xff
 8801a1a:	d00d      	beq.n	8801a38 <TranslateHandleChar+0xec>
 8801a1c:	000a      	movs	r2, r1
 8801a1e:	2300      	movs	r3, #0
 8801a20:	4650      	mov	r0, sl
 8801a22:	2af9      	cmp	r2, #249	@ 0xf9
 8801a24:	d030      	beq.n	8801a88 <TranslateHandleChar+0x13c>
 8801a26:	2afd      	cmp	r2, #253	@ 0xfd
 8801a28:	d059      	beq.n	8801ade <TranslateHandleChar+0x192>
 8801a2a:	2af9      	cmp	r2, #249	@ 0xf9
 8801a2c:	d835      	bhi.n	8801a9a <TranslateHandleChar+0x14e>
 8801a2e:	3301      	adds	r3, #1
 8801a30:	5cc2      	ldrb	r2, [r0, r3]
 8801a32:	2aff      	cmp	r2, #255	@ 0xff
 8801a34:	d1f5      	bne.n	8801a22 <TranslateHandleChar+0xd6>
 8801a36:	4682      	mov	sl, r0
 8801a38:	4b5e      	ldr	r3, [pc, #376]	@ (8801bb4 <TranslateHandleChar+0x268>)
 8801a3a:	4699      	mov	r9, r3
 8801a3c:	4b5e      	ldr	r3, [pc, #376]	@ (8801bb8 <TranslateHandleChar+0x26c>)
 8801a3e:	9501      	str	r5, [sp, #4]
 8801a40:	2721      	movs	r7, #33	@ 0x21
 8801a42:	4655      	mov	r5, sl
 8801a44:	2600      	movs	r6, #0
 8801a46:	4698      	mov	r8, r3
 8801a48:	46a2      	mov	sl, r4
 8801a4a:	29ff      	cmp	r1, #255	@ 0xff
 8801a4c:	d100      	bne.n	8801a50 <TranslateHandleChar+0x104>
 8801a4e:	e09e      	b.n	8801b8e <TranslateHandleChar+0x242>
 8801a50:	29f9      	cmp	r1, #249	@ 0xf9
 8801a52:	d05b      	beq.n	8801b0c <TranslateHandleChar+0x1c0>
 8801a54:	29fd      	cmp	r1, #253	@ 0xfd
 8801a56:	d100      	bne.n	8801a5a <TranslateHandleChar+0x10e>
 8801a58:	e082      	b.n	8801b60 <TranslateHandleChar+0x214>
 8801a5a:	1c74      	adds	r4, r6, #1
 8801a5c:	0423      	lsls	r3, r4, #16
 8801a5e:	002a      	movs	r2, r5
 8801a60:	4650      	mov	r0, sl
 8801a62:	0c1b      	lsrs	r3, r3, #16
 8801a64:	f7ff fdc0 	bl	88015e8 <slot_lookup_stream>
 8801a68:	2800      	cmp	r0, #0
 8801a6a:	d03d      	beq.n	8801ae8 <TranslateHandleChar+0x19c>
 8801a6c:	0026      	movs	r6, r4
 8801a6e:	3f01      	subs	r7, #1
 8801a70:	2f00      	cmp	r7, #0
 8801a72:	d100      	bne.n	8801a76 <TranslateHandleChar+0x12a>
 8801a74:	e08b      	b.n	8801b8e <TranslateHandleChar+0x242>
 8801a76:	5da9      	ldrb	r1, [r5, r6]
 8801a78:	e7e7      	b.n	8801a4a <TranslateHandleChar+0xfe>
 8801a7a:	7525      	strb	r5, [r4, #20]
 8801a7c:	7566      	strb	r6, [r4, #21]
 8801a7e:	e7aa      	b.n	88019d6 <TranslateHandleChar+0x8a>
 8801a80:	002b      	movs	r3, r5
 8801a82:	f7ff fdb1 	bl	88015e8 <slot_lookup_stream>
 8801a86:	e7a7      	b.n	88019d8 <TranslateHandleChar+0x8c>
 8801a88:	18c2      	adds	r2, r0, r3
 8801a8a:	7852      	ldrb	r2, [r2, #1]
 8801a8c:	2a00      	cmp	r2, #0
 8801a8e:	d104      	bne.n	8801a9a <TranslateHandleChar+0x14e>
 8801a90:	3201      	adds	r2, #1
 8801a92:	3304      	adds	r3, #4
 8801a94:	32ff      	adds	r2, #255	@ 0xff
 8801a96:	4293      	cmp	r3, r2
 8801a98:	d9ca      	bls.n	8801a30 <TranslateHandleChar+0xe4>
 8801a9a:	4682      	mov	sl, r0
 8801a9c:	4653      	mov	r3, sl
 8801a9e:	7423      	strb	r3, [r4, #16]
 8801aa0:	0a1b      	lsrs	r3, r3, #8
 8801aa2:	7463      	strb	r3, [r4, #17]
 8801aa4:	4653      	mov	r3, sl
 8801aa6:	0c1b      	lsrs	r3, r3, #16
 8801aa8:	74a3      	strb	r3, [r4, #18]
 8801aaa:	4653      	mov	r3, sl
 8801aac:	0e1b      	lsrs	r3, r3, #24
 8801aae:	74e3      	strb	r3, [r4, #19]
 8801ab0:	2300      	movs	r3, #0
 8801ab2:	7523      	strb	r3, [r4, #20]
 8801ab4:	7563      	strb	r3, [r4, #21]
 8801ab6:	e78e      	b.n	88019d6 <TranslateHandleChar+0x8a>
 8801ab8:	2b1a      	cmp	r3, #26
 8801aba:	d905      	bls.n	8801ac8 <TranslateHandleChar+0x17c>
 8801abc:	3b03      	subs	r3, #3
 8801abe:	0219      	lsls	r1, r3, #8
 8801ac0:	4301      	orrs	r1, r0
 8801ac2:	0409      	lsls	r1, r1, #16
 8801ac4:	0c09      	lsrs	r1, r1, #16
 8801ac6:	e779      	b.n	88019bc <TranslateHandleChar+0x70>
 8801ac8:	3b02      	subs	r3, #2
 8801aca:	0219      	lsls	r1, r3, #8
 8801acc:	23e0      	movs	r3, #224	@ 0xe0
 8801ace:	4301      	orrs	r1, r0
 8801ad0:	0409      	lsls	r1, r1, #16
 8801ad2:	0c09      	lsrs	r1, r1, #16
 8801ad4:	015b      	lsls	r3, r3, #5
 8801ad6:	4299      	cmp	r1, r3
 8801ad8:	d300      	bcc.n	8801adc <TranslateHandleChar+0x190>
 8801ada:	e77c      	b.n	88019d6 <TranslateHandleChar+0x8a>
 8801adc:	e76e      	b.n	88019bc <TranslateHandleChar+0x70>
 8801ade:	3302      	adds	r3, #2
 8801ae0:	3203      	adds	r2, #3
 8801ae2:	4293      	cmp	r3, r2
 8801ae4:	d8d9      	bhi.n	8801a9a <TranslateHandleChar+0x14e>
 8801ae6:	e7a3      	b.n	8801a30 <TranslateHandleChar+0xe4>
 8801ae8:	4650      	mov	r0, sl
 8801aea:	5da9      	ldrb	r1, [r5, r6]
 8801aec:	f7ff f880 	bl	8800bf0 <DrawGlyph>
 8801af0:	2800      	cmp	r0, #0
 8801af2:	d1bb      	bne.n	8801a6c <TranslateHandleChar+0x120>
 8801af4:	465b      	mov	r3, fp
 8801af6:	2280      	movs	r2, #128	@ 0x80
 8801af8:	681b      	ldr	r3, [r3, #0]
 8801afa:	4654      	mov	r4, sl
 8801afc:	0452      	lsls	r2, r2, #17
 8801afe:	4293      	cmp	r3, r2
 8801b00:	d300      	bcc.n	8801b04 <TranslateHandleChar+0x1b8>
 8801b02:	e768      	b.n	88019d6 <TranslateHandleChar+0x8a>
 8801b04:	4a2a      	ldr	r2, [pc, #168]	@ (8801bb0 <TranslateHandleChar+0x264>)
 8801b06:	4692      	mov	sl, r2
 8801b08:	449a      	add	sl, r3
 8801b0a:	e7c7      	b.n	8801a9c <TranslateHandleChar+0x150>
 8801b0c:	19aa      	adds	r2, r5, r6
 8801b0e:	7853      	ldrb	r3, [r2, #1]
 8801b10:	2b00      	cmp	r3, #0
 8801b12:	d1a2      	bne.n	8801a5a <TranslateHandleChar+0x10e>
 8801b14:	241d      	movs	r4, #29
 8801b16:	7893      	ldrb	r3, [r2, #2]
 8801b18:	1e58      	subs	r0, r3, #1
 8801b1a:	4684      	mov	ip, r0
 8801b1c:	0600      	lsls	r0, r0, #24
 8801b1e:	78d2      	ldrb	r2, [r2, #3]
 8801b20:	0e00      	lsrs	r0, r0, #24
 8801b22:	4284      	cmp	r4, r0
 8801b24:	d3e6      	bcc.n	8801af4 <TranslateHandleChar+0x1a8>
 8801b26:	4291      	cmp	r1, r2
 8801b28:	d3e4      	bcc.n	8801af4 <TranslateHandleChar+0x1a8>
 8801b2a:	2b06      	cmp	r3, #6
 8801b2c:	d0e2      	beq.n	8801af4 <TranslateHandleChar+0x1a8>
 8801b2e:	2b1b      	cmp	r3, #27
 8801b30:	d0e0      	beq.n	8801af4 <TranslateHandleChar+0x1a8>
 8801b32:	2b05      	cmp	r3, #5
 8801b34:	d81e      	bhi.n	8801b74 <TranslateHandleChar+0x228>
 8801b36:	4663      	mov	r3, ip
 8801b38:	021c      	lsls	r4, r3, #8
 8801b3a:	4314      	orrs	r4, r2
 8801b3c:	0421      	lsls	r1, r4, #16
 8801b3e:	0c09      	lsrs	r1, r1, #16
 8801b40:	4653      	mov	r3, sl
 8801b42:	2207      	movs	r2, #7
 8801b44:	7a9b      	ldrb	r3, [r3, #10]
 8801b46:	401a      	ands	r2, r3
 8801b48:	3a02      	subs	r2, #2
 8801b4a:	4253      	negs	r3, r2
 8801b4c:	415a      	adcs	r2, r3
 8801b4e:	2301      	movs	r3, #1
 8801b50:	4252      	negs	r2, r2
 8801b52:	439a      	bics	r2, r3
 8801b54:	4650      	mov	r0, sl
 8801b56:	320c      	adds	r2, #12
 8801b58:	f7fe ffa4 	bl	8800aa4 <chs_print>
 8801b5c:	3604      	adds	r6, #4
 8801b5e:	e786      	b.n	8801a6e <TranslateHandleChar+0x122>
 8801b60:	19ab      	adds	r3, r5, r6
 8801b62:	7858      	ldrb	r0, [r3, #1]
 8801b64:	f000 f889 	bl	8801c7a <GetStringWidth+0xbe>
 8801b68:	0001      	movs	r1, r0
 8801b6a:	4650      	mov	r0, sl
 8801b6c:	f000 f884 	bl	8801c78 <GetStringWidth+0xbc>
 8801b70:	3602      	adds	r6, #2
 8801b72:	e77c      	b.n	8801a6e <TranslateHandleChar+0x122>
 8801b74:	2b1a      	cmp	r3, #26
 8801b76:	d812      	bhi.n	8801b9e <TranslateHandleChar+0x252>
 8801b78:	3b02      	subs	r3, #2
 8801b7a:	021b      	lsls	r3, r3, #8
 8801b7c:	431a      	orrs	r2, r3
 8801b7e:	23e0      	movs	r3, #224	@ 0xe0
 8801b80:	0411      	lsls	r1, r2, #16
 8801b82:	0c09      	lsrs	r1, r1, #16
 8801b84:	015b      	lsls	r3, r3, #5
 8801b86:	4299      	cmp	r1, r3
 8801b88:	d3da      	bcc.n	8801b40 <TranslateHandleChar+0x1f4>
 8801b8a:	3604      	adds	r6, #4
 8801b8c:	e76f      	b.n	8801a6e <TranslateHandleChar+0x122>
 8801b8e:	4654      	mov	r4, sl
 8801b90:	9d01      	ldr	r5, [sp, #4]
 8801b92:	3503      	adds	r5, #3
 8801b94:	042b      	lsls	r3, r5, #16
 8801b96:	0e1b      	lsrs	r3, r3, #24
 8801b98:	7525      	strb	r5, [r4, #20]
 8801b9a:	7563      	strb	r3, [r4, #21]
 8801b9c:	e71b      	b.n	88019d6 <TranslateHandleChar+0x8a>
 8801b9e:	3b03      	subs	r3, #3
 8801ba0:	021b      	lsls	r3, r3, #8
 8801ba2:	4313      	orrs	r3, r2
 8801ba4:	041b      	lsls	r3, r3, #16
 8801ba6:	0c19      	lsrs	r1, r3, #16
 8801ba8:	e7ca      	b.n	8801b40 <TranslateHandleChar+0x1f4>
 8801baa:	46c0      	nop			@ (mov r8, r8)
 8801bac:	08810000 	.word	0x08810000
 8801bb0:	08820000 	.word	0x08820000
 8801bb4:	080046d5 	.word	0x080046d5
 8801bb8:	08002db5 	.word	0x08002db5

08801bbc <GetStringWidth>:
 8801bbc:	b5f0      	push	{r4, r5, r6, r7, lr}
 8801bbe:	46c6      	mov	lr, r8
 8801bc0:	0005      	movs	r5, r0
 8801bc2:	2300      	movs	r3, #0
 8801bc4:	2000      	movs	r0, #0
 8801bc6:	b500      	push	{lr}
 8801bc8:	2900      	cmp	r1, #0
 8801bca:	d105      	bne.n	8801bd8 <GetStringWidth+0x1c>
 8801bcc:	e029      	b.n	8801c22 <GetStringWidth+0x66>
 8801bce:	0023      	movs	r3, r4
 8801bd0:	2af9      	cmp	r2, #249	@ 0xf9
 8801bd2:	d92e      	bls.n	8801c32 <GetStringWidth+0x76>
 8801bd4:	4299      	cmp	r1, r3
 8801bd6:	d924      	bls.n	8801c22 <GetStringWidth+0x66>
 8801bd8:	5cea      	ldrb	r2, [r5, r3]
 8801bda:	2aff      	cmp	r2, #255	@ 0xff
 8801bdc:	d021      	beq.n	8801c22 <GetStringWidth+0x66>
 8801bde:	1c5c      	adds	r4, r3, #1
 8801be0:	2af9      	cmp	r2, #249	@ 0xf9
 8801be2:	d1f4      	bne.n	8801bce <GetStringWidth+0x12>
 8801be4:	1cda      	adds	r2, r3, #3
 8801be6:	428a      	cmp	r2, r1
 8801be8:	d223      	bcs.n	8801c32 <GetStringWidth+0x76>
 8801bea:	5d2c      	ldrb	r4, [r5, r4]
 8801bec:	2c00      	cmp	r4, #0
 8801bee:	d01d      	beq.n	8801c2c <GetStringWidth+0x70>
 8801bf0:	18ec      	adds	r4, r5, r3
 8801bf2:	78a6      	ldrb	r6, [r4, #2]
 8801bf4:	5cac      	ldrb	r4, [r5, r2]
 8801bf6:	0236      	lsls	r6, r6, #8
 8801bf8:	4334      	orrs	r4, r6
 8801bfa:	2680      	movs	r6, #128	@ 0x80
 8801bfc:	0422      	lsls	r2, r4, #16
 8801bfe:	1412      	asrs	r2, r2, #16
 8801c00:	01b6      	lsls	r6, r6, #6
 8801c02:	42b4      	cmp	r4, r6
 8801c04:	d212      	bcs.n	8801c2c <GetStringWidth+0x70>
 8801c06:	4c1a      	ldr	r4, [pc, #104]	@ (8801c70 <GetStringWidth+0xb4>)
 8801c08:	46a4      	mov	ip, r4
 8801c0a:	0092      	lsls	r2, r2, #2
 8801c0c:	4462      	add	r2, ip
 8801c0e:	6816      	ldr	r6, [r2, #0]
 8801c10:	2280      	movs	r2, #128	@ 0x80
 8801c12:	270c      	movs	r7, #12
 8801c14:	0452      	lsls	r2, r2, #17
 8801c16:	4296      	cmp	r6, r2
 8801c18:	d30e      	bcc.n	8801c38 <GetStringWidth+0x7c>
 8801c1a:	19c0      	adds	r0, r0, r7
 8801c1c:	3304      	adds	r3, #4
 8801c1e:	4299      	cmp	r1, r3
 8801c20:	d8da      	bhi.n	8801bd8 <GetStringWidth+0x1c>
 8801c22:	bc80      	pop	{r7}
 8801c24:	46b8      	mov	r8, r7
 8801c26:	bcf0      	pop	{r4, r5, r6, r7}
 8801c28:	bc02      	pop	{r1}
 8801c2a:	4708      	bx	r1
 8801c2c:	300c      	adds	r0, #12
 8801c2e:	3304      	adds	r3, #4
 8801c30:	e7f5      	b.n	8801c1e <GetStringWidth+0x62>
 8801c32:	0023      	movs	r3, r4
 8801c34:	3008      	adds	r0, #8
 8801c36:	e7cd      	b.n	8801bd4 <GetStringWidth+0x18>
 8801c38:	4a0e      	ldr	r2, [pc, #56]	@ (8801c74 <GetStringWidth+0xb8>)
 8801c3a:	4694      	mov	ip, r2
 8801c3c:	4466      	add	r6, ip
 8801c3e:	46b0      	mov	r8, r6
 8801c40:	2700      	movs	r7, #0
 8801c42:	2200      	movs	r2, #0
 8801c44:	e005      	b.n	8801c52 <GetStringWidth+0x96>
 8801c46:	0032      	movs	r2, r6
 8801c48:	2cf9      	cmp	r4, #249	@ 0xf9
 8801c4a:	d800      	bhi.n	8801c4e <GetStringWidth+0x92>
 8801c4c:	3708      	adds	r7, #8
 8801c4e:	2aff      	cmp	r2, #255	@ 0xff
 8801c50:	d8e3      	bhi.n	8801c1a <GetStringWidth+0x5e>
 8801c52:	4644      	mov	r4, r8
 8801c54:	5ca4      	ldrb	r4, [r4, r2]
 8801c56:	2cff      	cmp	r4, #255	@ 0xff
 8801c58:	d0df      	beq.n	8801c1a <GetStringWidth+0x5e>
 8801c5a:	1c56      	adds	r6, r2, #1
 8801c5c:	2cf9      	cmp	r4, #249	@ 0xf9
 8801c5e:	d1f2      	bne.n	8801c46 <GetStringWidth+0x8a>
 8801c60:	0034      	movs	r4, r6
 8801c62:	4646      	mov	r6, r8
 8801c64:	5d34      	ldrb	r4, [r6, r4]
 8801c66:	2c00      	cmp	r4, #0
 8801c68:	d100      	bne.n	8801c6c <GetStringWidth+0xb0>
 8801c6a:	370c      	adds	r7, #12
 8801c6c:	3204      	adds	r2, #4
 8801c6e:	e7ee      	b.n	8801c4e <GetStringWidth+0x92>
 8801c70:	08810000 	.word	0x08810000
 8801c74:	08820000 	.word	0x08820000
 8801c78:	4740      	bx	r8
 8801c7a:	4748      	bx	r9
 8801c7c:	4750      	bx	sl
 8801c7e:	4758      	bx	fp

08801c80 <v6_scene_lookup>:
 8801c80:	4b09      	ldr	r3, [pc, #36]	@ (8801ca8 <v6_scene_lookup+0x28>)
 8801c82:	4298      	cmp	r0, r3
 8801c84:	d104      	bne.n	8801c90 <v6_scene_lookup+0x10>
 8801c86:	4b09      	ldr	r3, [pc, #36]	@ (8801cac <v6_scene_lookup+0x2c>)
 8801c88:	4299      	cmp	r1, r3
 8801c8a:	d00a      	beq.n	8801ca2 <v6_scene_lookup+0x22>
 8801c8c:	2000      	movs	r0, #0
 8801c8e:	4770      	bx	lr
 8801c90:	4b07      	ldr	r3, [pc, #28]	@ (8801cb0 <v6_scene_lookup+0x30>)
 8801c92:	4298      	cmp	r0, r3
 8801c94:	d1fa      	bne.n	8801c8c <v6_scene_lookup+0xc>
 8801c96:	4b05      	ldr	r3, [pc, #20]	@ (8801cac <v6_scene_lookup+0x2c>)
 8801c98:	2000      	movs	r0, #0
 8801c9a:	4299      	cmp	r1, r3
 8801c9c:	d1f7      	bne.n	8801c8e <v6_scene_lookup+0xe>
 8801c9e:	4805      	ldr	r0, [pc, #20]	@ (8801cb4 <v6_scene_lookup+0x34>)
 8801ca0:	e7f5      	b.n	8801c8e <v6_scene_lookup+0xe>
 8801ca2:	4805      	ldr	r0, [pc, #20]	@ (8801cb8 <v6_scene_lookup+0x38>)
 8801ca4:	e7f3      	b.n	8801c8e <v6_scene_lookup+0xe>
 8801ca6:	46c0      	nop			@ (mov r8, r8)
 8801ca8:	081bb7b4 	.word	0x081bb7b4
 8801cac:	0202e658 	.word	0x0202e658
 8801cb0:	081bb7e4 	.word	0x081bb7e4
 8801cb4:	088023bc 	.word	0x088023bc
 8801cb8:	088023ac 	.word	0x088023ac

08801cbc <v6_scene_font>:
 8801cbc:	4b18      	ldr	r3, [pc, #96]	@ (8801d20 <v6_scene_font+0x64>)
 8801cbe:	b510      	push	{r4, lr}
 8801cc0:	4298      	cmp	r0, r3
 8801cc2:	d106      	bne.n	8801cd2 <v6_scene_font+0x16>
 8801cc4:	4b17      	ldr	r3, [pc, #92]	@ (8801d24 <v6_scene_font+0x68>)
 8801cc6:	4299      	cmp	r1, r3
 8801cc8:	d025      	beq.n	8801d16 <v6_scene_font+0x5a>
 8801cca:	2000      	movs	r0, #0
 8801ccc:	bc10      	pop	{r4}
 8801cce:	bc02      	pop	{r1}
 8801cd0:	4708      	bx	r1
 8801cd2:	4b15      	ldr	r3, [pc, #84]	@ (8801d28 <v6_scene_font+0x6c>)
 8801cd4:	4298      	cmp	r0, r3
 8801cd6:	d1f8      	bne.n	8801cca <v6_scene_font+0xe>
 8801cd8:	4b12      	ldr	r3, [pc, #72]	@ (8801d24 <v6_scene_font+0x68>)
 8801cda:	2000      	movs	r0, #0
 8801cdc:	4299      	cmp	r1, r3
 8801cde:	d1f5      	bne.n	8801ccc <v6_scene_font+0x10>
 8801ce0:	4912      	ldr	r1, [pc, #72]	@ (8801d2c <v6_scene_font+0x70>)
 8801ce2:	688b      	ldr	r3, [r1, #8]
 8801ce4:	2b00      	cmp	r3, #0
 8801ce6:	d0f0      	beq.n	8801cca <v6_scene_font+0xe>
 8801ce8:	7b0c      	ldrb	r4, [r1, #12]
 8801cea:	2c00      	cmp	r4, #0
 8801cec:	d0ed      	beq.n	8801cca <v6_scene_font+0xe>
 8801cee:	2100      	movs	r1, #0
 8801cf0:	e003      	b.n	8801cfa <v6_scene_font+0x3e>
 8801cf2:	3101      	adds	r1, #1
 8801cf4:	3302      	adds	r3, #2
 8801cf6:	42a1      	cmp	r1, r4
 8801cf8:	d2e7      	bcs.n	8801cca <v6_scene_font+0xe>
 8801cfa:	7818      	ldrb	r0, [r3, #0]
 8801cfc:	4290      	cmp	r0, r2
 8801cfe:	d9f8      	bls.n	8801cf2 <v6_scene_font+0x36>
 8801d00:	7858      	ldrb	r0, [r3, #1]
 8801d02:	280f      	cmp	r0, #15
 8801d04:	d809      	bhi.n	8801d1a <v6_scene_font+0x5e>
 8801d06:	0003      	movs	r3, r0
 8801d08:	22fd      	movs	r2, #253	@ 0xfd
 8801d0a:	3b0a      	subs	r3, #10
 8801d0c:	4213      	tst	r3, r2
 8801d0e:	d0dd      	beq.n	8801ccc <v6_scene_font+0x10>
 8801d10:	280d      	cmp	r0, #13
 8801d12:	d1da      	bne.n	8801cca <v6_scene_font+0xe>
 8801d14:	e7da      	b.n	8801ccc <v6_scene_font+0x10>
 8801d16:	4906      	ldr	r1, [pc, #24]	@ (8801d30 <v6_scene_font+0x74>)
 8801d18:	e7e3      	b.n	8801ce2 <v6_scene_font+0x26>
 8801d1a:	200c      	movs	r0, #12
 8801d1c:	e7d6      	b.n	8801ccc <v6_scene_font+0x10>
 8801d1e:	46c0      	nop			@ (mov r8, r8)
 8801d20:	081bb7b4 	.word	0x081bb7b4
 8801d24:	0202e658 	.word	0x0202e658
 8801d28:	081bb7e4 	.word	0x081bb7e4
 8801d2c:	088023bc 	.word	0x088023bc
 8801d30:	088023ac 	.word	0x088023ac

08801d34 <MapNamePopup_CalcLeftPx>:
 8801d34:	2114      	movs	r1, #20
 8801d36:	b510      	push	{r4, lr}
 8801d38:	f7ff ff40 	bl	8801bbc <GetStringWidth>
 8801d3c:	1e43      	subs	r3, r0, #1
 8801d3e:	2b4e      	cmp	r3, #78	@ 0x4e
 8801d40:	d807      	bhi.n	8801d52 <MapNamePopup_CalcLeftPx+0x1e>
 8801d42:	2350      	movs	r3, #80	@ 0x50
 8801d44:	1a18      	subs	r0, r3, r0
 8801d46:	0840      	lsrs	r0, r0, #1
 8801d48:	3004      	adds	r0, #4
 8801d4a:	08c0      	lsrs	r0, r0, #3
 8801d4c:	bc10      	pop	{r4}
 8801d4e:	bc02      	pop	{r1}
 8801d50:	4708      	bx	r1
 8801d52:	2000      	movs	r0, #0
 8801d54:	e7fa      	b.n	8801d4c <MapNamePopup_CalcLeftPx+0x18>
 8801d56:	46c0      	nop			@ (mov r8, r8)

08801d58 <HealthboxNickCpusetCtrl>:
 8801d58:	4800      	ldr	r0, [pc, #0]	@ (8801d5c <HealthboxNickCpusetCtrl+0x4>)
 8801d5a:	4770      	bx	lr
 8801d5c:	04000006 	.word	0x04000006

08801d60 <HealthboxNickCpusetWords>:
 8801d60:	2006      	movs	r0, #6
 8801d62:	4770      	bx	lr

08801d64 <HealthboxNickCpusetCtrlStock>:
 8801d64:	4800      	ldr	r0, [pc, #0]	@ (8801d68 <HealthboxNickCpusetCtrlStock+0x4>)
 8801d66:	4770      	bx	lr
 8801d68:	04000008 	.word	0x04000008

08801d6c <append_stream>:
 8801d6c:	b530      	push	{r4, r5, lr}
 8801d6e:	0004      	movs	r4, r0
 8801d70:	0008      	movs	r0, r1
 8801d72:	2a00      	cmp	r2, #0
 8801d74:	d011      	beq.n	8801d9a <append_stream+0x2e>
 8801d76:	1d05      	adds	r5, r0, #4
 8801d78:	2d3f      	cmp	r5, #63	@ 0x3f
 8801d7a:	d80e      	bhi.n	8801d9a <append_stream+0x2e>
 8801d7c:	7811      	ldrb	r1, [r2, #0]
 8801d7e:	1e4b      	subs	r3, r1, #1
 8801d80:	061b      	lsls	r3, r3, #24
 8801d82:	0e1b      	lsrs	r3, r3, #24
 8801d84:	2bfd      	cmp	r3, #253	@ 0xfd
 8801d86:	d808      	bhi.n	8801d9a <append_stream+0x2e>
 8801d88:	1823      	adds	r3, r4, r0
 8801d8a:	7019      	strb	r1, [r3, #0]
 8801d8c:	3001      	adds	r0, #1
 8801d8e:	29f9      	cmp	r1, #249	@ 0xf9
 8801d90:	d006      	beq.n	8801da0 <append_stream+0x34>
 8801d92:	1d05      	adds	r5, r0, #4
 8801d94:	3201      	adds	r2, #1
 8801d96:	2d3f      	cmp	r5, #63	@ 0x3f
 8801d98:	d9f0      	bls.n	8801d7c <append_stream+0x10>
 8801d9a:	bc30      	pop	{r4, r5}
 8801d9c:	bc02      	pop	{r1}
 8801d9e:	4708      	bx	r1
 8801da0:	7851      	ldrb	r1, [r2, #1]
 8801da2:	5421      	strb	r1, [r4, r0]
 8801da4:	7891      	ldrb	r1, [r2, #2]
 8801da6:	7099      	strb	r1, [r3, #2]
 8801da8:	78d1      	ldrb	r1, [r2, #3]
 8801daa:	0028      	movs	r0, r5
 8801dac:	70d9      	strb	r1, [r3, #3]
 8801dae:	3204      	adds	r2, #4
 8801db0:	e7e1      	b.n	8801d76 <append_stream+0xa>
 8801db2:	46c0      	nop			@ (mov r8, r8)

08801db4 <UnusedPrintMonName_hook_C>:
 8801db4:	b5f0      	push	{r4, r5, r6, r7, lr}
 8801db6:	46c6      	mov	lr, r8
 8801db8:	b500      	push	{lr}
 8801dba:	000c      	movs	r4, r1
 8801dbc:	4b69      	ldr	r3, [pc, #420]	@ (8801f64 <UnusedPrintMonName_hook_C+0x1b0>)
 8801dbe:	7801      	ldrb	r1, [r0, #0]
 8801dc0:	0015      	movs	r5, r2
 8801dc2:	781f      	ldrb	r7, [r3, #0]
 8801dc4:	b090      	sub	sp, #64	@ 0x40
 8801dc6:	29f9      	cmp	r1, #249	@ 0xf9
 8801dc8:	d061      	beq.n	8801e8e <UnusedPrintMonName_hook_C+0xda>
 8801dca:	2fac      	cmp	r7, #172	@ 0xac
 8801dcc:	d000      	beq.n	8801dd0 <UnusedPrintMonName_hook_C+0x1c>
 8801dce:	e085      	b.n	8801edc <UnusedPrintMonName_hook_C+0x128>
 8801dd0:	2300      	movs	r3, #0
 8801dd2:	0019      	movs	r1, r3
 8801dd4:	4a64      	ldr	r2, [pc, #400]	@ (8801f68 <UnusedPrintMonName_hook_C+0x1b4>)
 8801dd6:	188e      	adds	r6, r1, r2
 8801dd8:	7832      	ldrb	r2, [r6, #0]
 8801dda:	3301      	adds	r3, #1
 8801ddc:	2aac      	cmp	r2, #172	@ 0xac
 8801dde:	d0f8      	beq.n	8801dd2 <UnusedPrintMonName_hook_C+0x1e>
 8801de0:	2af9      	cmp	r2, #249	@ 0xf9
 8801de2:	d100      	bne.n	8801de6 <UnusedPrintMonName_hook_C+0x32>
 8801de4:	e074      	b.n	8801ed0 <UnusedPrintMonName_hook_C+0x11c>
 8801de6:	2800      	cmp	r0, #0
 8801de8:	d100      	bne.n	8801dec <UnusedPrintMonName_hook_C+0x38>
 8801dea:	e0a5      	b.n	8801f38 <UnusedPrintMonName_hook_C+0x184>
 8801dec:	7801      	ldrb	r1, [r0, #0]
 8801dee:	1e4b      	subs	r3, r1, #1
 8801df0:	061b      	lsls	r3, r3, #24
 8801df2:	0002      	movs	r2, r0
 8801df4:	0e1b      	lsrs	r3, r3, #24
 8801df6:	2bfd      	cmp	r3, #253	@ 0xfd
 8801df8:	d900      	bls.n	8801dfc <UnusedPrintMonName_hook_C+0x48>
 8801dfa:	e074      	b.n	8801ee6 <UnusedPrintMonName_hook_C+0x132>
 8801dfc:	2700      	movs	r7, #0
 8801dfe:	e006      	b.n	8801e0e <UnusedPrintMonName_hook_C+0x5a>
 8801e00:	7841      	ldrb	r1, [r0, #1]
 8801e02:	1e4b      	subs	r3, r1, #1
 8801e04:	061b      	lsls	r3, r3, #24
 8801e06:	3001      	adds	r0, #1
 8801e08:	0e1b      	lsrs	r3, r3, #24
 8801e0a:	2bfd      	cmp	r3, #253	@ 0xfd
 8801e0c:	d809      	bhi.n	8801e22 <UnusedPrintMonName_hook_C+0x6e>
 8801e0e:	29f9      	cmp	r1, #249	@ 0xf9
 8801e10:	d1f6      	bne.n	8801e00 <UnusedPrintMonName_hook_C+0x4c>
 8801e12:	7901      	ldrb	r1, [r0, #4]
 8801e14:	1e4b      	subs	r3, r1, #1
 8801e16:	061b      	lsls	r3, r3, #24
 8801e18:	3004      	adds	r0, #4
 8801e1a:	3701      	adds	r7, #1
 8801e1c:	0e1b      	lsrs	r3, r3, #24
 8801e1e:	2bfd      	cmp	r3, #253	@ 0xfd
 8801e20:	d9f5      	bls.n	8801e0e <UnusedPrintMonName_hook_C+0x5a>
 8801e22:	2328      	movs	r3, #40	@ 0x28
 8801e24:	0079      	lsls	r1, r7, #1
 8801e26:	19c9      	adds	r1, r1, r7
 8801e28:	0089      	lsls	r1, r1, #2
 8801e2a:	1a5b      	subs	r3, r3, r1
 8801e2c:	43d9      	mvns	r1, r3
 8801e2e:	17c9      	asrs	r1, r1, #31
 8801e30:	400b      	ands	r3, r1
 8801e32:	3307      	adds	r3, #7
 8801e34:	10db      	asrs	r3, r3, #3
 8801e36:	2100      	movs	r1, #0
 8801e38:	4668      	mov	r0, sp
 8801e3a:	4698      	mov	r8, r3
 8801e3c:	f7ff ff96 	bl	8801d6c <append_stream>
 8801e40:	0032      	movs	r2, r6
 8801e42:	0001      	movs	r1, r0
 8801e44:	4668      	mov	r0, sp
 8801e46:	f7ff ff91 	bl	8801d6c <append_stream>
 8801e4a:	4643      	mov	r3, r8
 8801e4c:	466f      	mov	r7, sp
 8801e4e:	2b00      	cmp	r3, #0
 8801e50:	d01b      	beq.n	8801e8a <UnusedPrintMonName_hook_C+0xd6>
 8801e52:	4643      	mov	r3, r8
 8801e54:	181e      	adds	r6, r3, r0
 8801e56:	466b      	mov	r3, sp
 8801e58:	2200      	movs	r2, #0
 8801e5a:	1e59      	subs	r1, r3, #1
 8801e5c:	e003      	b.n	8801e66 <UnusedPrintMonName_hook_C+0xb2>
 8801e5e:	1843      	adds	r3, r0, r1
 8801e60:	701a      	strb	r2, [r3, #0]
 8801e62:	42b0      	cmp	r0, r6
 8801e64:	d011      	beq.n	8801e8a <UnusedPrintMonName_hook_C+0xd6>
 8801e66:	0003      	movs	r3, r0
 8801e68:	3001      	adds	r0, #1
 8801e6a:	283f      	cmp	r0, #63	@ 0x3f
 8801e6c:	d9f7      	bls.n	8801e5e <UnusedPrintMonName_hook_C+0xaa>
 8801e6e:	22ff      	movs	r2, #255	@ 0xff
 8801e70:	0021      	movs	r1, r4
 8801e72:	54fa      	strb	r2, [r7, r3]
 8801e74:	0038      	movs	r0, r7
 8801e76:	002a      	movs	r2, r5
 8801e78:	4b3c      	ldr	r3, [pc, #240]	@ (8801f6c <UnusedPrintMonName_hook_C+0x1b8>)
 8801e7a:	f000 f881 	bl	8801f80 <UnusedPrintMonName_hook_C+0x1cc>
 8801e7e:	b010      	add	sp, #64	@ 0x40
 8801e80:	bc80      	pop	{r7}
 8801e82:	46b8      	mov	r8, r7
 8801e84:	bcf0      	pop	{r4, r5, r6, r7}
 8801e86:	bc01      	pop	{r0}
 8801e88:	4700      	bx	r0
 8801e8a:	0003      	movs	r3, r0
 8801e8c:	e7ef      	b.n	8801e6e <UnusedPrintMonName_hook_C+0xba>
 8801e8e:	7842      	ldrb	r2, [r0, #1]
 8801e90:	2a80      	cmp	r2, #128	@ 0x80
 8801e92:	d02a      	beq.n	8801eea <UnusedPrintMonName_hook_C+0x136>
 8801e94:	2fac      	cmp	r7, #172	@ 0xac
 8801e96:	d09b      	beq.n	8801dd0 <UnusedPrintMonName_hook_C+0x1c>
 8801e98:	0002      	movs	r2, r0
 8801e9a:	001e      	movs	r6, r3
 8801e9c:	2ff9      	cmp	r7, #249	@ 0xf9
 8801e9e:	d1ad      	bne.n	8801dfc <UnusedPrintMonName_hook_C+0x48>
 8801ea0:	4a31      	ldr	r2, [pc, #196]	@ (8801f68 <UnusedPrintMonName_hook_C+0x1b4>)
 8801ea2:	7812      	ldrb	r2, [r2, #0]
 8801ea4:	2a80      	cmp	r2, #128	@ 0x80
 8801ea6:	d1a1      	bne.n	8801dec <UnusedPrintMonName_hook_C+0x38>
 8801ea8:	2300      	movs	r3, #0
 8801eaa:	4a31      	ldr	r2, [pc, #196]	@ (8801f70 <UnusedPrintMonName_hook_C+0x1bc>)
 8801eac:	4931      	ldr	r1, [pc, #196]	@ (8801f74 <UnusedPrintMonName_hook_C+0x1c0>)
 8801eae:	5c9a      	ldrb	r2, [r3, r2]
 8801eb0:	5c5b      	ldrb	r3, [r3, r1]
 8801eb2:	0212      	lsls	r2, r2, #8
 8801eb4:	4313      	orrs	r3, r2
 8801eb6:	4a30      	ldr	r2, [pc, #192]	@ (8801f78 <UnusedPrintMonName_hook_C+0x1c4>)
 8801eb8:	4694      	mov	ip, r2
 8801eba:	009b      	lsls	r3, r3, #2
 8801ebc:	4463      	add	r3, ip
 8801ebe:	681e      	ldr	r6, [r3, #0]
 8801ec0:	2380      	movs	r3, #128	@ 0x80
 8801ec2:	045b      	lsls	r3, r3, #17
 8801ec4:	429e      	cmp	r6, r3
 8801ec6:	d245      	bcs.n	8801f54 <UnusedPrintMonName_hook_C+0x1a0>
 8801ec8:	4b2c      	ldr	r3, [pc, #176]	@ (8801f7c <UnusedPrintMonName_hook_C+0x1c8>)
 8801eca:	469c      	mov	ip, r3
 8801ecc:	4466      	add	r6, ip
 8801ece:	e78a      	b.n	8801de6 <UnusedPrintMonName_hook_C+0x32>
 8801ed0:	4a27      	ldr	r2, [pc, #156]	@ (8801f70 <UnusedPrintMonName_hook_C+0x1bc>)
 8801ed2:	5c8a      	ldrb	r2, [r1, r2]
 8801ed4:	2a80      	cmp	r2, #128	@ 0x80
 8801ed6:	d000      	beq.n	8801eda <UnusedPrintMonName_hook_C+0x126>
 8801ed8:	e785      	b.n	8801de6 <UnusedPrintMonName_hook_C+0x32>
 8801eda:	e7e6      	b.n	8801eaa <UnusedPrintMonName_hook_C+0xf6>
 8801edc:	001e      	movs	r6, r3
 8801ede:	2ff9      	cmp	r7, #249	@ 0xf9
 8801ee0:	d000      	beq.n	8801ee4 <UnusedPrintMonName_hook_C+0x130>
 8801ee2:	e784      	b.n	8801dee <UnusedPrintMonName_hook_C+0x3a>
 8801ee4:	e7dc      	b.n	8801ea0 <UnusedPrintMonName_hook_C+0xec>
 8801ee6:	2700      	movs	r7, #0
 8801ee8:	e79b      	b.n	8801e22 <UnusedPrintMonName_hook_C+0x6e>
 8801eea:	78c2      	ldrb	r2, [r0, #3]
 8801eec:	7881      	ldrb	r1, [r0, #2]
 8801eee:	0212      	lsls	r2, r2, #8
 8801ef0:	4311      	orrs	r1, r2
 8801ef2:	0209      	lsls	r1, r1, #8
 8801ef4:	0a12      	lsrs	r2, r2, #8
 8801ef6:	430a      	orrs	r2, r1
 8801ef8:	491f      	ldr	r1, [pc, #124]	@ (8801f78 <UnusedPrintMonName_hook_C+0x1c4>)
 8801efa:	468c      	mov	ip, r1
 8801efc:	0412      	lsls	r2, r2, #16
 8801efe:	0b92      	lsrs	r2, r2, #14
 8801f00:	4462      	add	r2, ip
 8801f02:	6810      	ldr	r0, [r2, #0]
 8801f04:	2280      	movs	r2, #128	@ 0x80
 8801f06:	0452      	lsls	r2, r2, #17
 8801f08:	4290      	cmp	r0, r2
 8801f0a:	d20a      	bcs.n	8801f22 <UnusedPrintMonName_hook_C+0x16e>
 8801f0c:	4a1b      	ldr	r2, [pc, #108]	@ (8801f7c <UnusedPrintMonName_hook_C+0x1c8>)
 8801f0e:	4694      	mov	ip, r2
 8801f10:	4460      	add	r0, ip
 8801f12:	2fac      	cmp	r7, #172	@ 0xac
 8801f14:	d100      	bne.n	8801f18 <UnusedPrintMonName_hook_C+0x164>
 8801f16:	e75b      	b.n	8801dd0 <UnusedPrintMonName_hook_C+0x1c>
 8801f18:	2ff9      	cmp	r7, #249	@ 0xf9
 8801f1a:	d01d      	beq.n	8801f58 <UnusedPrintMonName_hook_C+0x1a4>
 8801f1c:	001e      	movs	r6, r3
 8801f1e:	7801      	ldrb	r1, [r0, #0]
 8801f20:	e765      	b.n	8801dee <UnusedPrintMonName_hook_C+0x3a>
 8801f22:	2000      	movs	r0, #0
 8801f24:	2fac      	cmp	r7, #172	@ 0xac
 8801f26:	d100      	bne.n	8801f2a <UnusedPrintMonName_hook_C+0x176>
 8801f28:	e752      	b.n	8801dd0 <UnusedPrintMonName_hook_C+0x1c>
 8801f2a:	001e      	movs	r6, r3
 8801f2c:	2ff9      	cmp	r7, #249	@ 0xf9
 8801f2e:	d103      	bne.n	8801f38 <UnusedPrintMonName_hook_C+0x184>
 8801f30:	4a0d      	ldr	r2, [pc, #52]	@ (8801f68 <UnusedPrintMonName_hook_C+0x1b4>)
 8801f32:	7812      	ldrb	r2, [r2, #0]
 8801f34:	2a80      	cmp	r2, #128	@ 0x80
 8801f36:	d0b7      	beq.n	8801ea8 <UnusedPrintMonName_hook_C+0xf4>
 8801f38:	2200      	movs	r2, #0
 8801f3a:	2100      	movs	r1, #0
 8801f3c:	4668      	mov	r0, sp
 8801f3e:	f7ff ff15 	bl	8801d6c <append_stream>
 8801f42:	0032      	movs	r2, r6
 8801f44:	0001      	movs	r1, r0
 8801f46:	4668      	mov	r0, sp
 8801f48:	f7ff ff10 	bl	8801d6c <append_stream>
 8801f4c:	2305      	movs	r3, #5
 8801f4e:	466f      	mov	r7, sp
 8801f50:	4698      	mov	r8, r3
 8801f52:	e77e      	b.n	8801e52 <UnusedPrintMonName_hook_C+0x9e>
 8801f54:	2600      	movs	r6, #0
 8801f56:	e746      	b.n	8801de6 <UnusedPrintMonName_hook_C+0x32>
 8801f58:	4a03      	ldr	r2, [pc, #12]	@ (8801f68 <UnusedPrintMonName_hook_C+0x1b4>)
 8801f5a:	7812      	ldrb	r2, [r2, #0]
 8801f5c:	2a80      	cmp	r2, #128	@ 0x80
 8801f5e:	d0a3      	beq.n	8801ea8 <UnusedPrintMonName_hook_C+0xf4>
 8801f60:	001e      	movs	r6, r3
 8801f62:	e743      	b.n	8801dec <UnusedPrintMonName_hook_C+0x38>
 8801f64:	083e9688 	.word	0x083e9688
 8801f68:	083e9689 	.word	0x083e9689
 8801f6c:	0806f16d 	.word	0x0806f16d
 8801f70:	083e968a 	.word	0x083e968a
 8801f74:	083e968b 	.word	0x083e968b
 8801f78:	08810000 	.word	0x08810000
 8801f7c:	08820000 	.word	0x08820000
 8801f80:	4718      	bx	r3
 8801f82:	46c0      	nop			@ (mov r8, r8)

08801f84 <DrawOptionMenuChoice_hook_C>:
 8801f84:	b5f0      	push	{r4, r5, r6, r7, lr}
 8801f86:	46c6      	mov	lr, r8
 8801f88:	b500      	push	{lr}
 8801f8a:	4694      	mov	ip, r2
 8801f8c:	7802      	ldrb	r2, [r0, #0]
 8801f8e:	061f      	lsls	r7, r3, #24
 8801f90:	0005      	movs	r5, r0
 8801f92:	b086      	sub	sp, #24
 8801f94:	0e3f      	lsrs	r7, r7, #24
 8801f96:	2af9      	cmp	r2, #249	@ 0xf9
 8801f98:	d027      	beq.n	8801fea <DrawOptionMenuChoice_hook_C+0x66>
 8801f9a:	2300      	movs	r3, #0
 8801f9c:	a801      	add	r0, sp, #4
 8801f9e:	4698      	mov	r8, r3
 8801fa0:	2aff      	cmp	r2, #255	@ 0xff
 8801fa2:	d00d      	beq.n	8801fc0 <DrawOptionMenuChoice_hook_C+0x3c>
 8801fa4:	4646      	mov	r6, r8
 8801fa6:	0014      	movs	r4, r2
 8801fa8:	2300      	movs	r3, #0
 8801faa:	1986      	adds	r6, r0, r6
 8801fac:	54f4      	strb	r4, [r6, r3]
 8801fae:	3301      	adds	r3, #1
 8801fb0:	5cec      	ldrb	r4, [r5, r3]
 8801fb2:	2cff      	cmp	r4, #255	@ 0xff
 8801fb4:	d001      	beq.n	8801fba <DrawOptionMenuChoice_hook_C+0x36>
 8801fb6:	2b0f      	cmp	r3, #15
 8801fb8:	d1f8      	bne.n	8801fac <DrawOptionMenuChoice_hook_C+0x28>
 8801fba:	4443      	add	r3, r8
 8801fbc:	2af9      	cmp	r2, #249	@ 0xf9
 8801fbe:	d000      	beq.n	8801fc2 <DrawOptionMenuChoice_hook_C+0x3e>
 8801fc0:	7087      	strb	r7, [r0, #2]
 8801fc2:	22ff      	movs	r2, #255	@ 0xff
 8801fc4:	54c2      	strb	r2, [r0, r3]
 8801fc6:	2301      	movs	r3, #1
 8801fc8:	4d0b      	ldr	r5, [pc, #44]	@ (8801ff8 <DrawOptionMenuChoice_hook_C+0x74>)
 8801fca:	4c0c      	ldr	r4, [pc, #48]	@ (8801ffc <DrawOptionMenuChoice_hook_C+0x78>)
 8801fcc:	702f      	strb	r7, [r5, #0]
 8801fce:	4662      	mov	r2, ip
 8801fd0:	7023      	strb	r3, [r4, #0]
 8801fd2:	4b0b      	ldr	r3, [pc, #44]	@ (8802000 <DrawOptionMenuChoice_hook_C+0x7c>)
 8801fd4:	f000 f818 	bl	8802008 <DrawOptionMenuChoice_hook_C+0x84>
 8801fd8:	2300      	movs	r3, #0
 8801fda:	702b      	strb	r3, [r5, #0]
 8801fdc:	7023      	strb	r3, [r4, #0]
 8801fde:	b006      	add	sp, #24
 8801fe0:	bc80      	pop	{r7}
 8801fe2:	46b8      	mov	r8, r7
 8801fe4:	bcf0      	pop	{r4, r5, r6, r7}
 8801fe6:	bc01      	pop	{r0}
 8801fe8:	4700      	bx	r0
 8801fea:	4b06      	ldr	r3, [pc, #24]	@ (8802004 <DrawOptionMenuChoice_hook_C+0x80>)
 8801fec:	a801      	add	r0, sp, #4
 8801fee:	8003      	strh	r3, [r0, #0]
 8801ff0:	2303      	movs	r3, #3
 8801ff2:	7087      	strb	r7, [r0, #2]
 8801ff4:	4698      	mov	r8, r3
 8801ff6:	e7d5      	b.n	8801fa4 <DrawOptionMenuChoice_hook_C+0x20>
 8801ff8:	0203ffd0 	.word	0x0203ffd0
 8801ffc:	0203ffd1 	.word	0x0203ffd1
 8802000:	0806f16d 	.word	0x0806f16d
 8802004:	000005fc 	.word	0x000005fc
 8802008:	4718      	bx	r3
 880200a:	46c0      	nop			@ (mov r8, r8)

0880200c <sGlyphShiftAmounts>:
 880200c:	0000 0000 0020 0000 0004 0000 001c 0000     .... ...........
 880201c:	0008 0000 0018 0000 000c 0000 0014 0000     ................
 880202c:	0010 0000 0010 0000 0014 0000 000c 0000     ................
 880203c:	0018 0000 0008 0000 001c 0000 0004 0000     ................

0880204c <sGlyphMasks>:
 880204c:	ffff ffff ffff ffff 0000 0000 ffff ffff     ................
 880205c:	ffff ffff 0000 0000 ffff ffff ffff ffff     ................
 880206c:	0000 0000 ffff ffff ffff ffff 0000 0000     ................
 880207c:	ffff ffff ffff ffff 0000 0000 ffff ffff     ................
 880208c:	ffff ffff 0000 0000 ffff ffff ffff ffff     ................
 880209c:	0000 0000 ffff ffff ffff ffff 0000 0000     ................
 88020ac:	0000 0000 ffff ffff fff0 ffff 000f 0000     ................
 88020bc:	ffff ffff ff00 ffff 00ff 0000 ffff ffff     ................
 88020cc:	f000 ffff 0fff 0000 ffff ffff 0000 ffff     ................
 88020dc:	ffff 0000 ffff ffff 0000 fff0 ffff 000f     ................
 88020ec:	ffff ffff 0000 ff00 ffff 00ff ffff ffff     ................
 88020fc:	0000 f000 ffff 0fff ffff ffff 0000 0000     ................
 880210c:	0000 0000 ffff ffff ff00 ffff 000f 0000     ................
 880211c:	ffff ffff f000 ffff 00ff 0000 ffff ffff     ................
 880212c:	0000 ffff 0fff 0000 ffff ffff 0000 fff0     ................
 880213c:	ffff 0000 ffff ffff 0000 ff00 ffff 000f     ................
 880214c:	ffff ffff 0000 f000 ffff 00ff ffff ffff     ................
 880215c:	0000 0000 ffff 0fff fff0 ffff 0000 0000     ................
 880216c:	0000 0000 ffff ffff f000 ffff 000f 0000     ................
 880217c:	ffff ffff 0000 ffff 00ff 0000 ffff ffff     ................
 880218c:	0000 fff0 0fff 0000 ffff ffff 0000 ff00     ................
 880219c:	ffff 0000 ffff ffff 0000 f000 ffff 000f     ................
 88021ac:	ffff ffff 0000 0000 ffff 00ff fff0 ffff     ................
 88021bc:	0000 0000 ffff 0fff ff00 ffff 0000 0000     ................
 88021cc:	0000 0000 ffff ffff 0000 ffff 000f 0000     ................
 88021dc:	ffff ffff 0000 fff0 00ff 0000 ffff ffff     ................
 88021ec:	0000 ff00 0fff 0000 ffff ffff 0000 f000     ................
 88021fc:	ffff 0000 ffff ffff 0000 0000 ffff 000f     ................
 880220c:	fff0 ffff 0000 0000 ffff 00ff ff00 ffff     ................
 880221c:	0000 0000 ffff 0fff f000 ffff 0000 0000     ................
 880222c:	0000 0000 ffff ffff 0000 fff0 000f 0000     ................
 880223c:	ffff ffff 0000 ff00 00ff 0000 ffff ffff     ................
 880224c:	0000 f000 0fff 0000 ffff ffff 0000 0000     ................
 880225c:	ffff 0000 fff0 ffff 0000 0000 ffff 000f     ................
 880226c:	ff00 ffff 0000 0000 ffff 00ff f000 ffff     ................
 880227c:	0000 0000 ffff 0fff 0000 ffff 0000 0000     ................
 880228c:	0000 0000 ffff ffff 0000 ff00 000f 0000     ................
 880229c:	ffff ffff 0000 f000 00ff 0000 ffff ffff     ................
 88022ac:	0000 0000 0fff 0000 fff0 ffff 0000 0000     ................
 88022bc:	ffff 0000 ff00 ffff 0000 0000 ffff 000f     ................
 88022cc:	f000 ffff 0000 0000 ffff 00ff 0000 ffff     ................
 88022dc:	0000 0000 ffff 0fff 0000 fff0 0000 0000     ................
 88022ec:	0000 0000 ffff ffff 0000 f000 000f 0000     ................
 88022fc:	ffff ffff 0000 0000 00ff 0000 fff0 ffff     ................
 880230c:	0000 0000 0fff 0000 ff00 ffff 0000 0000     ................
 880231c:	ffff 0000 f000 ffff 0000 0000 ffff 000f     ................
 880232c:	0000 ffff 0000 0000 ffff 00ff 0000 fff0     ................
 880233c:	0000 0000 ffff 0fff 0000 ff00 0000 0000     ................
 880234c:	0000 0000 ffff ffff 0000 0000 000f 0000     ................
 880235c:	fff0 ffff 0000 0000 00ff 0000 ff00 ffff     ................
 880236c:	0000 0000 0fff 0000 f000 ffff 0000 0000     ................
 880237c:	ffff 0000 0000 ffff 0000 0000 ffff 000f     ................
 880238c:	0000 fff0 0000 0000 ffff 00ff 0000 ff00     ................
 880239c:	0000 0000 ffff 0fff 0000 f000 0000 0000     ................

088023ac <kV6Scenes>:
 88023ac:	b7b4 081b e658 0202 23d0 0880 0003 0000     ....X....#......
 88023bc:	b7e4 081b e658 0202 23d0 0880 0003 0000     ....X....#......

088023cc <kV6SceneN>:
 88023cc:	0002 0000                                   ....

088023d0 <kPokeNavZones>:
 88023d0:	0d04 0c05 0dff 0000                         ........
