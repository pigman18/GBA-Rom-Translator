
.tmp/txt.bin:     file format binary


Disassembly of section .data:

08002000 <.data>:
 8002000:	1c18      	adds	r0, r3, #0
 8002002:	302a      	adds	r0, #42	@ 0x2a
 8002004:	7801      	ldrb	r1, [r0, #0]
 8002006:	6898      	ldr	r0, [r3, #8]
 8002008:	0089      	lsls	r1, r1, #2
 800200a:	1809      	adds	r1, r1, r0
 800200c:	1c18      	adds	r0, r3, #0
 800200e:	302b      	adds	r0, #43	@ 0x2b
 8002010:	7800      	ldrb	r0, [r0, #0]
 8002012:	6809      	ldr	r1, [r1, #0]
 8002014:	0080      	lsls	r0, r0, #2
 8002016:	1840      	adds	r0, r0, r1
 8002018:	8802      	ldrh	r2, [r0, #0]
 800201a:	2100      	movs	r1, #0
 800201c:	5e40      	ldrsh	r0, [r0, r1]
 800201e:	2800      	cmp	r0, #0
 8002020:	da00      	bge.n	0x8002024
 8002022:	2200      	movs	r2, #0
 8002024:	1c18      	adds	r0, r3, #0
 8002026:	3040      	adds	r0, #64	@ 0x40
 8002028:	8801      	ldrh	r1, [r0, #0]
 800202a:	1889      	adds	r1, r1, r2
 800202c:	4a04      	ldr	r2, [pc, #16]	@ (0x8002040)
 800202e:	1c10      	adds	r0, r2, #0
 8002030:	4001      	ands	r1, r0
 8002032:	889a      	ldrh	r2, [r3, #4]
 8002034:	4803      	ldr	r0, [pc, #12]	@ (0x8002044)
 8002036:	4010      	ands	r0, r2
 8002038:	4308      	orrs	r0, r1
 800203a:	8098      	strh	r0, [r3, #4]
 800203c:	bc01      	pop	{r0}
 800203e:	4700      	bx	r0
 8002040:	03ff      	lsls	r7, r7, #15
 8002042:	0000      	movs	r0, r0
 8002044:	fc00 ffff 			@ <UNDEFINED> instruction: 0xfc00ffff
 8002048:	b510      	push	{r4, lr}
 800204a:	490a      	ldr	r1, [pc, #40]	@ (0x8002074)
 800204c:	2000      	movs	r0, #0
 800204e:	7008      	strb	r0, [r1, #0]
 8002050:	4909      	ldr	r1, [pc, #36]	@ (0x8002078)
 8002052:	2000      	movs	r0, #0
 8002054:	6008      	str	r0, [r1, #0]
 8002056:	f7fe ffbb 	bl	0x8000fd0
 800205a:	2400      	movs	r4, #0
 800205c:	1c20      	adds	r0, r4, #0
 800205e:	f7ff fe09 	bl	0x8001c74
 8002062:	1c60      	adds	r0, r4, #1
 8002064:	0600      	lsls	r0, r0, #24
 8002066:	0e04      	lsrs	r4, r0, #24
 8002068:	2c1f      	cmp	r4, #31
 800206a:	d9f7      	bls.n	0x800205c
 800206c:	bc10      	pop	{r4}
 800206e:	bc01      	pop	{r0}
 8002070:	4700      	bx	r0
 8002072:	0000      	movs	r0, r0
 8002074:	11c8      	asrs	r0, r1, #7
 8002076:	0202      	lsls	r2, r0, #8
 8002078:	2864      	cmp	r0, #100	@ 0x64
 800207a:	0300      	lsls	r0, r0, #12
 800207c:	b510      	push	{r4, lr}
 800207e:	2200      	movs	r2, #0
 8002080:	2101      	movs	r1, #1
 8002082:	4806      	ldr	r0, [pc, #24]	@ (0x800209c)
 8002084:	6804      	ldr	r4, [r0, #0]
 8002086:	1c03      	adds	r3, r0, #0
 8002088:	1c20      	adds	r0, r4, #0
 800208a:	4008      	ands	r0, r1
 800208c:	2800      	cmp	r0, #0
 800208e:	d107      	bne.n	0x80020a0
 8002090:	6818      	ldr	r0, [r3, #0]
 8002092:	4308      	orrs	r0, r1
 8002094:	6018      	str	r0, [r3, #0]
 8002096:	1c10      	adds	r0, r2, #0
 8002098:	e009      	b.n	0x80020ae
 800209a:	0000      	movs	r0, r0
 800209c:	2864      	cmp	r0, #100	@ 0x64
 800209e:	0300      	lsls	r0, r0, #12
 80020a0:	1c50      	adds	r0, r2, #1
 80020a2:	0600      	lsls	r0, r0, #24
 80020a4:	0e02      	lsrs	r2, r0, #24
 80020a6:	0049      	lsls	r1, r1, #1
 80020a8:	2a1f      	cmp	r2, #31
 80020aa:	d9ed      	bls.n	0x8002088
 80020ac:	20ff      	movs	r0, #255	@ 0xff
 80020ae:	bc10      	pop	{r4}
 80020b0:	bc02      	pop	{r1}
 80020b2:	4708      	bx	r1
 80020b4:	b500      	push	{lr}
 80020b6:	b081      	sub	sp, #4
 80020b8:	0600      	lsls	r0, r0, #24
 80020ba:	0e02      	lsrs	r2, r0, #24
 80020bc:	2000      	movs	r0, #0
 80020be:	2101      	movs	r1, #1
 80020c0:	4b0b      	ldr	r3, [pc, #44]	@ (0x80020f0)
 80020c2:	4290      	cmp	r0, r2
 80020c4:	d205      	bcs.n	0x80020d2
 80020c6:	3001      	adds	r0, #1
 80020c8:	0600      	lsls	r0, r0, #24
 80020ca:	0e00      	lsrs	r0, r0, #24
 80020cc:	0049      	lsls	r1, r1, #1
 80020ce:	4290      	cmp	r0, r2
 80020d0:	d3f9      	bcc.n	0x80020c6
 80020d2:	6818      	ldr	r0, [r3, #0]
 80020d4:	4388      	bics	r0, r1
 80020d6:	6018      	str	r0, [r3, #0]
 80020d8:	2180      	movs	r1, #128	@ 0x80
 80020da:	0049      	lsls	r1, r1, #1
 80020dc:	9100      	str	r1, [sp, #0]
 80020de:	1c10      	adds	r0, r2, #0
 80020e0:	2200      	movs	r2, #0
 80020e2:	2300      	movs	r3, #0
 80020e4:	f7fe ff8a 	bl	0x8000ffc
 80020e8:	b001      	add	sp, #4
 80020ea:	bc01      	pop	{r0}
 80020ec:	4700      	bx	r0
 80020ee:	0000      	movs	r0, r0
 80020f0:	2864      	cmp	r0, #100	@ 0x64
 80020f2:	0300      	lsls	r0, r0, #12
 80020f4:	b530      	push	{r4, r5, lr}
 80020f6:	1c04      	adds	r4, r0, #0
 80020f8:	f7ff ffc0 	bl	0x800207c
 80020fc:	0600      	lsls	r0, r0, #24
 80020fe:	0e05      	lsrs	r5, r0, #24
 8002100:	2dff      	cmp	r5, #255	@ 0xff
 8002102:	d01b      	beq.n	0x800213c
 8002104:	7863      	ldrb	r3, [r4, #1]
 8002106:	0999      	lsrs	r1, r3, #6
 8002108:	78e2      	ldrb	r2, [r4, #3]
 800210a:	0992      	lsrs	r2, r2, #6
 800210c:	079b      	lsls	r3, r3, #30
 800210e:	0f9b      	lsrs	r3, r3, #30
 8002110:	1c20      	adds	r0, r4, #0
 8002112:	f7fe ff8d 	bl	0x8001030
 8002116:	201f      	movs	r0, #31
 8002118:	1c29      	adds	r1, r5, #0
 800211a:	4001      	ands	r1, r0
 800211c:	0049      	lsls	r1, r1, #1
 800211e:	78e2      	ldrb	r2, [r4, #3]
 8002120:	203f      	movs	r0, #63	@ 0x3f
 8002122:	4240      	negs	r0, r0
 8002124:	4010      	ands	r0, r2
 8002126:	4308      	orrs	r0, r1
 8002128:	70e0      	strb	r0, [r4, #3]
 800212a:	1c22      	adds	r2, r4, #0
 800212c:	323f      	adds	r2, #63	@ 0x3f
 800212e:	7810      	ldrb	r0, [r2, #0]
 8002130:	2108      	movs	r1, #8
 8002132:	4308      	orrs	r0, r1
 8002134:	7010      	strb	r0, [r2, #0]
 8002136:	1c28      	adds	r0, r5, #0
 8002138:	f7ff fd9c 	bl	0x8001c74
 800213c:	bc30      	pop	{r4, r5}
 800213e:	bc01      	pop	{r0}
 8002140:	4700      	bx	r0
 8002142:	0000      	movs	r0, r0
 8002144:	b570      	push	{r4, r5, r6, lr}
 8002146:	4646      	mov	r6, r8
 8002148:	b440      	push	{r6}
 800214a:	b084      	sub	sp, #16
 800214c:	1c06      	adds	r6, r0, #0
 800214e:	1c08      	adds	r0, r1, #0
 8002150:	1c14      	adds	r4, r2, #0
 8002152:	1c1d      	adds	r5, r3, #0
 8002154:	0636      	lsls	r6, r6, #24
 8002156:	0e36      	lsrs	r6, r6, #24
 8002158:	0424      	lsls	r4, r4, #16
 800215a:	0c24      	lsrs	r4, r4, #16
 800215c:	042d      	lsls	r5, r5, #16
 800215e:	0c2d      	lsrs	r5, r5, #16
 8002160:	0400      	lsls	r0, r0, #16
 8002162:	1400      	asrs	r0, r0, #16
 8002164:	f7ff fe24 	bl	0x8001db0
 8002168:	0400      	lsls	r0, r0, #16
 800216a:	0c00      	lsrs	r0, r0, #16
 800216c:	4913      	ldr	r1, [pc, #76]	@ (0x80021bc)
 800216e:	4688      	mov	r8, r1
 8002170:	9900      	ldr	r1, [sp, #0]
 8002172:	4642      	mov	r2, r8
 8002174:	4011      	ands	r1, r2
 8002176:	4301      	orrs	r1, r0
 8002178:	9100      	str	r1, [sp, #0]
 800217a:	0424      	lsls	r4, r4, #16
 800217c:	1424      	asrs	r4, r4, #16
 800217e:	1c20      	adds	r0, r4, #0
 8002180:	f7ff fe16 	bl	0x8001db0
 8002184:	0400      	lsls	r0, r0, #16
 8002186:	4a0e      	ldr	r2, [pc, #56]	@ (0x80021c0)
 8002188:	9900      	ldr	r1, [sp, #0]
 800218a:	4011      	ands	r1, r2
 800218c:	4301      	orrs	r1, r0
 800218e:	9100      	str	r1, [sp, #0]
 8002190:	9801      	ldr	r0, [sp, #4]
 8002192:	4641      	mov	r1, r8
 8002194:	4008      	ands	r0, r1
 8002196:	4328      	orrs	r0, r5
 8002198:	9001      	str	r0, [sp, #4]
 800219a:	ac02      	add	r4, sp, #8
 800219c:	4668      	mov	r0, sp
 800219e:	1c21      	adds	r1, r4, #0
 80021a0:	2201      	movs	r2, #1
 80021a2:	2302      	movs	r3, #2
 80021a4:	f1af f87c 	bl	0x81b12a0
 80021a8:	1c30      	adds	r0, r6, #0
 80021aa:	1c21      	adds	r1, r4, #0
 80021ac:	f7ff fce6 	bl	0x8001b7c
 80021b0:	b004      	add	sp, #16
 80021b2:	bc08      	pop	{r3}
 80021b4:	4698      	mov	r8, r3
 80021b6:	bc70      	pop	{r4, r5, r6}
 80021b8:	bc01      	pop	{r0}
 80021ba:	4700      	bx	r0
 80021bc:	0000      	movs	r0, r0
 80021be:	ffff ffff 			@ <UNDEFINED> instruction: 0xffffffff
 80021c2:	0000      	movs	r0, r0
 80021c4:	b570      	push	{r4, r5, r6, lr}
 80021c6:	1c05      	adds	r5, r0, #0
 80021c8:	88a8      	ldrh	r0, [r5, #4]
 80021ca:	0940      	lsrs	r0, r0, #5
 80021cc:	f7fe ff52 	bl	0x8001074
 80021d0:	0404      	lsls	r4, r0, #16
 80021d2:	1426      	asrs	r6, r4, #16
 80021d4:	2e00      	cmp	r6, #0
 80021d6:	db13      	blt.n	0x8002200
 80021d8:	88e8      	ldrh	r0, [r5, #6]
 80021da:	0c24      	lsrs	r4, r4, #16
 80021dc:	88aa      	ldrh	r2, [r5, #4]
 80021de:	0952      	lsrs	r2, r2, #5
 80021e0:	1c21      	adds	r1, r4, #0
 80021e2:	f000 f8d5 	bl	0x8002390
 80021e6:	6828      	ldr	r0, [r5, #0]
 80021e8:	0171      	lsls	r1, r6, #5
 80021ea:	4a04      	ldr	r2, [pc, #16]	@ (0x80021fc)
 80021ec:	1889      	adds	r1, r1, r2
 80021ee:	88aa      	ldrh	r2, [r5, #4]
 80021f0:	0852      	lsrs	r2, r2, #1
 80021f2:	f1af f84f 	bl	0x81b1294
 80021f6:	1c20      	adds	r0, r4, #0
 80021f8:	e003      	b.n	0x8002202
 80021fa:	0000      	movs	r0, r0
 80021fc:	0000      	movs	r0, r0
 80021fe:	0601      	lsls	r1, r0, #24
 8002200:	2000      	movs	r0, #0
 8002202:	bc70      	pop	{r4, r5, r6}
 8002204:	bc02      	pop	{r1}
 8002206:	4708      	bx	r1
 8002208:	b530      	push	{r4, r5, lr}
 800220a:	1c05      	adds	r5, r0, #0
 800220c:	2400      	movs	r4, #0
 800220e:	6828      	ldr	r0, [r5, #0]
 8002210:	2800      	cmp	r0, #0
 8002212:	d00b      	beq.n	0x800222c
 8002214:	00e0      	lsls	r0, r4, #3
 8002216:	1828      	adds	r0, r5, r0
 8002218:	f7ff ffd4 	bl	0x80021c4
 800221c:	1c60      	adds	r0, r4, #1
 800221e:	0600      	lsls	r0, r0, #24
 8002220:	0e04      	lsrs	r4, r0, #24
 8002222:	00e0      	lsls	r0, r4, #3
 8002224:	1940      	adds	r0, r0, r5
 8002226:	6800      	ldr	r0, [r0, #0]
 8002228:	2800      	cmp	r0, #0
 800222a:	d1f3      	bne.n	0x8002214
 800222c:	bc30      	pop	{r4, r5}
 800222e:	bc01      	pop	{r0}
 8002230:	4700      	bx	r0
 8002232:	0000      	movs	r0, r0
 8002234:	b5f0      	push	{r4, r5, r6, r7, lr}
 8002236:	4647      	mov	r7, r8
 8002238:	b480      	push	{r7}
 800223a:	0400      	lsls	r0, r0, #16
 800223c:	0c00      	lsrs	r0, r0, #16
 800223e:	f000 f86b 	bl	0x8002318
 8002242:	0600      	lsls	r0, r0, #24
 8002244:	0e04      	lsrs	r4, r0, #24
 8002246:	2cff      	cmp	r4, #255	@ 0xff
 8002248:	d023      	beq.n	0x8002292
 800224a:	4814      	ldr	r0, [pc, #80]	@ (0x800229c)
 800224c:	00a1      	lsls	r1, r4, #2
 800224e:	180a      	adds	r2, r1, r0
 8002250:	3002      	adds	r0, #2
 8002252:	1809      	adds	r1, r1, r0
 8002254:	8808      	ldrh	r0, [r1, #0]
 8002256:	8813      	ldrh	r3, [r2, #0]
 8002258:	1818      	adds	r0, r3, r0
 800225a:	4911      	ldr	r1, [pc, #68]	@ (0x80022a0)
 800225c:	4688      	mov	r8, r1
 800225e:	0065      	lsls	r5, r4, #1
 8002260:	4283      	cmp	r3, r0
 8002262:	da12      	bge.n	0x800228a
 8002264:	490f      	ldr	r1, [pc, #60]	@ (0x80022a4)
 8002266:	468c      	mov	ip, r1
 8002268:	2607      	movs	r6, #7
 800226a:	2701      	movs	r7, #1
 800226c:	1c04      	adds	r4, r0, #0
 800226e:	08da      	lsrs	r2, r3, #3
 8002270:	4462      	add	r2, ip
 8002272:	1c18      	adds	r0, r3, #0
 8002274:	4030      	ands	r0, r6
 8002276:	1c39      	adds	r1, r7, #0
 8002278:	4081      	lsls	r1, r0
 800227a:	7810      	ldrb	r0, [r2, #0]
 800227c:	4388      	bics	r0, r1
 800227e:	7010      	strb	r0, [r2, #0]
 8002280:	1c58      	adds	r0, r3, #1
 8002282:	0400      	lsls	r0, r0, #16
 8002284:	0c03      	lsrs	r3, r0, #16
 8002286:	42a3      	cmp	r3, r4
 8002288:	dbf1      	blt.n	0x800226e
 800228a:	4640      	mov	r0, r8
 800228c:	1829      	adds	r1, r5, r0
 800228e:	4806      	ldr	r0, [pc, #24]	@ (0x80022a8)
 8002290:	8008      	strh	r0, [r1, #0]
 8002292:	bc08      	pop	{r3}
 8002294:	4698      	mov	r8, r3
 8002296:	bcf0      	pop	{r4, r5, r6, r7}
 8002298:	bc01      	pop	{r0}
 800229a:	4700      	bx	r0
 800229c:	0080      	lsls	r0, r0, #2
 800229e:	0300      	lsls	r0, r0, #12
 80022a0:	0000      	movs	r0, r0
 80022a2:	0300      	lsls	r0, r0, #12
 80022a4:	23c0      	movs	r3, #192	@ 0xc0
 80022a6:	0300      	lsls	r0, r0, #12
 80022a8:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 80022ac:	b5f0      	push	{r4, r5, r6, r7, lr}
 80022ae:	2200      	movs	r2, #0
 80022b0:	4f0b      	ldr	r7, [pc, #44]	@ (0x80022e0)
 80022b2:	480c      	ldr	r0, [pc, #48]	@ (0x80022e4)
 80022b4:	1c06      	adds	r6, r0, #0
 80022b6:	4c0c      	ldr	r4, [pc, #48]	@ (0x80022e8)
 80022b8:	2300      	movs	r3, #0
 80022ba:	1ca5      	adds	r5, r4, #2
 80022bc:	0051      	lsls	r1, r2, #1
 80022be:	19c9      	adds	r1, r1, r7
 80022c0:	8808      	ldrh	r0, [r1, #0]
 80022c2:	4330      	orrs	r0, r6
 80022c4:	8008      	strh	r0, [r1, #0]
 80022c6:	0091      	lsls	r1, r2, #2
 80022c8:	1908      	adds	r0, r1, r4
 80022ca:	8003      	strh	r3, [r0, #0]
 80022cc:	1949      	adds	r1, r1, r5
 80022ce:	800b      	strh	r3, [r1, #0]
 80022d0:	1c50      	adds	r0, r2, #1
 80022d2:	0600      	lsls	r0, r0, #24
 80022d4:	0e02      	lsrs	r2, r0, #24
 80022d6:	2a3f      	cmp	r2, #63	@ 0x3f
 80022d8:	d9f0      	bls.n	0x80022bc
 80022da:	bcf0      	pop	{r4, r5, r6, r7}
 80022dc:	bc01      	pop	{r0}
 80022de:	4700      	bx	r0
 80022e0:	0000      	movs	r0, r0
 80022e2:	0300      	lsls	r0, r0, #12
 80022e4:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 80022e8:	0080      	lsls	r0, r0, #2
 80022ea:	0300      	lsls	r0, r0, #12
 80022ec:	b500      	push	{lr}
 80022ee:	0400      	lsls	r0, r0, #16
 80022f0:	0c00      	lsrs	r0, r0, #16
 80022f2:	f000 f811 	bl	0x8002318
 80022f6:	0600      	lsls	r0, r0, #24
 80022f8:	0e01      	lsrs	r1, r0, #24
 80022fa:	29ff      	cmp	r1, #255	@ 0xff
 80022fc:	d006      	beq.n	0x800230c
 80022fe:	4802      	ldr	r0, [pc, #8]	@ (0x8002308)
 8002300:	0089      	lsls	r1, r1, #2
 8002302:	1809      	adds	r1, r1, r0
 8002304:	8808      	ldrh	r0, [r1, #0]
 8002306:	e002      	b.n	0x800230e
 8002308:	0080      	lsls	r0, r0, #2
 800230a:	0300      	lsls	r0, r0, #12
 800230c:	4801      	ldr	r0, [pc, #4]	@ (0x8002314)
 800230e:	bc02      	pop	{r1}
 8002310:	4708      	bx	r1
 8002312:	0000      	movs	r0, r0
 8002314:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 8002318:	b500      	push	{lr}
 800231a:	0400      	lsls	r0, r0, #16
 800231c:	0c02      	lsrs	r2, r0, #16
 800231e:	2100      	movs	r1, #0
 8002320:	4b03      	ldr	r3, [pc, #12]	@ (0x8002330)
 8002322:	0048      	lsls	r0, r1, #1
 8002324:	18c0      	adds	r0, r0, r3
 8002326:	8800      	ldrh	r0, [r0, #0]
 8002328:	4290      	cmp	r0, r2
 800232a:	d103      	bne.n	0x8002334
 800232c:	1c08      	adds	r0, r1, #0
 800232e:	e007      	b.n	0x8002340
 8002330:	0000      	movs	r0, r0
 8002332:	0300      	lsls	r0, r0, #12
 8002334:	1c48      	adds	r0, r1, #1
 8002336:	0600      	lsls	r0, r0, #24
 8002338:	0e01      	lsrs	r1, r0, #24
 800233a:	293f      	cmp	r1, #63	@ 0x3f
 800233c:	d9f1      	bls.n	0x8002322
 800233e:	20ff      	movs	r0, #255	@ 0xff
 8002340:	bc02      	pop	{r1}
 8002342:	4708      	bx	r1
 8002344:	b570      	push	{r4, r5, r6, lr}
 8002346:	0400      	lsls	r0, r0, #16
 8002348:	0c03      	lsrs	r3, r0, #16
 800234a:	2200      	movs	r2, #0
 800234c:	4e07      	ldr	r6, [pc, #28]	@ (0x800236c)
 800234e:	4d08      	ldr	r5, [pc, #32]	@ (0x8002370)
 8002350:	4c08      	ldr	r4, [pc, #32]	@ (0x8002374)
 8002352:	0050      	lsls	r0, r2, #1
 8002354:	1981      	adds	r1, r0, r6
 8002356:	8808      	ldrh	r0, [r1, #0]
 8002358:	42a8      	cmp	r0, r5
 800235a:	d00d      	beq.n	0x8002378
 800235c:	0090      	lsls	r0, r2, #2
 800235e:	1900      	adds	r0, r0, r4
 8002360:	8800      	ldrh	r0, [r0, #0]
 8002362:	4298      	cmp	r0, r3
 8002364:	d108      	bne.n	0x8002378
 8002366:	8808      	ldrh	r0, [r1, #0]
 8002368:	e00c      	b.n	0x8002384
 800236a:	0000      	movs	r0, r0
 800236c:	0000      	movs	r0, r0
 800236e:	0300      	lsls	r0, r0, #12
 8002370:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 8002374:	0080      	lsls	r0, r0, #2
 8002376:	0300      	lsls	r0, r0, #12
 8002378:	1c50      	adds	r0, r2, #1
 800237a:	0600      	lsls	r0, r0, #24
 800237c:	0e02      	lsrs	r2, r0, #24
 800237e:	2a3f      	cmp	r2, #63	@ 0x3f
 8002380:	d9e7      	bls.n	0x8002352
 8002382:	4802      	ldr	r0, [pc, #8]	@ (0x800238c)
 8002384:	bc70      	pop	{r4, r5, r6}
 8002386:	bc02      	pop	{r1}
 8002388:	4708      	bx	r1
 800238a:	0000      	movs	r0, r0
 800238c:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 8002390:	b570      	push	{r4, r5, r6, lr}
 8002392:	1c04      	adds	r4, r0, #0
 8002394:	1c0d      	adds	r5, r1, #0
 8002396:	1c16      	adds	r6, r2, #0
 8002398:	0424      	lsls	r4, r4, #16
 800239a:	0c24      	lsrs	r4, r4, #16
 800239c:	042d      	lsls	r5, r5, #16
 800239e:	0c2d      	lsrs	r5, r5, #16
 80023a0:	0436      	lsls	r6, r6, #16
 80023a2:	0c36      	lsrs	r6, r6, #16
 80023a4:	4809      	ldr	r0, [pc, #36]	@ (0x80023cc)
 80023a6:	f7ff ffb7 	bl	0x8002318
 80023aa:	0600      	lsls	r0, r0, #24
 80023ac:	0e00      	lsrs	r0, r0, #24
 80023ae:	4a08      	ldr	r2, [pc, #32]	@ (0x80023d0)
 80023b0:	0041      	lsls	r1, r0, #1
 80023b2:	1889      	adds	r1, r1, r2
 80023b4:	800c      	strh	r4, [r1, #0]
 80023b6:	4907      	ldr	r1, [pc, #28]	@ (0x80023d4)
 80023b8:	0080      	lsls	r0, r0, #2
 80023ba:	1842      	adds	r2, r0, r1
 80023bc:	8015      	strh	r5, [r2, #0]
 80023be:	3102      	adds	r1, #2
 80023c0:	1840      	adds	r0, r0, r1
 80023c2:	8006      	strh	r6, [r0, #0]
 80023c4:	bc70      	pop	{r4, r5, r6}
 80023c6:	bc01      	pop	{r0}
 80023c8:	4700      	bx	r0
 80023ca:	0000      	movs	r0, r0
 80023cc:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 80023d0:	0000      	movs	r0, r0
 80023d2:	0300      	lsls	r0, r0, #12
 80023d4:	0080      	lsls	r0, r0, #2
 80023d6:	0300      	lsls	r0, r0, #12
 80023d8:	b510      	push	{r4, lr}
 80023da:	490a      	ldr	r1, [pc, #40]	@ (0x8002404)
 80023dc:	2000      	movs	r0, #0
 80023de:	7008      	strb	r0, [r1, #0]
 80023e0:	2200      	movs	r2, #0
 80023e2:	4c09      	ldr	r4, [pc, #36]	@ (0x8002408)
 80023e4:	4809      	ldr	r0, [pc, #36]	@ (0x800240c)
 80023e6:	1c03      	adds	r3, r0, #0
 80023e8:	0050      	lsls	r0, r2, #1
 80023ea:	1900      	adds	r0, r0, r4
 80023ec:	8801      	ldrh	r1, [r0, #0]
 80023ee:	4319      	orrs	r1, r3
 80023f0:	8001      	strh	r1, [r0, #0]
 80023f2:	1c50      	adds	r0, r2, #1
 80023f4:	0600      	lsls	r0, r0, #24
 80023f6:	0e02      	lsrs	r2, r0, #24
 80023f8:	2a0f      	cmp	r2, #15
 80023fa:	d9f5      	bls.n	0x80023e8
 80023fc:	bc10      	pop	{r4}
 80023fe:	bc01      	pop	{r0}
 8002400:	4700      	bx	r0
 8002402:	0000      	movs	r0, r0
 8002404:	2868      	cmp	r0, #104	@ 0x68
 8002406:	0300      	lsls	r0, r0, #12
 8002408:	0300      	lsls	r0, r0, #12
 800240a:	0300      	lsls	r0, r0, #12
 800240c:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 8002410:	b530      	push	{r4, r5, lr}
 8002412:	1c05      	adds	r5, r0, #0
 8002414:	88a8      	ldrh	r0, [r5, #4]
 8002416:	f000 f85b 	bl	0x80024d0
 800241a:	0600      	lsls	r0, r0, #24
 800241c:	0e04      	lsrs	r4, r0, #24
 800241e:	2cff      	cmp	r4, #255	@ 0xff
 8002420:	d001      	beq.n	0x8002426
 8002422:	1c20      	adds	r0, r4, #0
 8002424:	e017      	b.n	0x8002456
 8002426:	4809      	ldr	r0, [pc, #36]	@ (0x800244c)
 8002428:	f000 f852 	bl	0x80024d0
 800242c:	0600      	lsls	r0, r0, #24
 800242e:	0e04      	lsrs	r4, r0, #24
 8002430:	2cff      	cmp	r4, #255	@ 0xff
 8002432:	d00f      	beq.n	0x8002454
 8002434:	4906      	ldr	r1, [pc, #24]	@ (0x8002450)
 8002436:	0060      	lsls	r0, r4, #1
 8002438:	1840      	adds	r0, r0, r1
 800243a:	88a9      	ldrh	r1, [r5, #4]
 800243c:	8001      	strh	r1, [r0, #0]
 800243e:	6828      	ldr	r0, [r5, #0]
 8002440:	0121      	lsls	r1, r4, #4
 8002442:	f000 f821 	bl	0x8002488
 8002446:	1c20      	adds	r0, r4, #0
 8002448:	e005      	b.n	0x8002456
 800244a:	0000      	movs	r0, r0
 800244c:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 8002450:	0300      	lsls	r0, r0, #12
 8002452:	0300      	lsls	r0, r0, #12
 8002454:	20ff      	movs	r0, #255	@ 0xff
 8002456:	bc30      	pop	{r4, r5}
 8002458:	bc02      	pop	{r1}
 800245a:	4708      	bx	r1
 800245c:	b530      	push	{r4, r5, lr}
 800245e:	1c05      	adds	r5, r0, #0
 8002460:	2400      	movs	r4, #0
 8002462:	e002      	b.n	0x800246a
 8002464:	1c60      	adds	r0, r4, #1
 8002466:	0600      	lsls	r0, r0, #24
 8002468:	0e04      	lsrs	r4, r0, #24
 800246a:	00e0      	lsls	r0, r4, #3
 800246c:	1941      	adds	r1, r0, r5
 800246e:	6808      	ldr	r0, [r1, #0]
 8002470:	2800      	cmp	r0, #0
 8002472:	d006      	beq.n	0x8002482
 8002474:	1c08      	adds	r0, r1, #0
 8002476:	f7ff ffcb 	bl	0x8002410
 800247a:	0600      	lsls	r0, r0, #24
 800247c:	0e00      	lsrs	r0, r0, #24
 800247e:	28ff      	cmp	r0, #255	@ 0xff
 8002480:	d1f0      	bne.n	0x8002464
 8002482:	bc30      	pop	{r4, r5}
 8002484:	bc01      	pop	{r0}
 8002486:	4700      	bx	r0
 8002488:	b500      	push	{lr}
 800248a:	0409      	lsls	r1, r1, #16
 800248c:	2280      	movs	r2, #128	@ 0x80
 800248e:	0452      	lsls	r2, r2, #17
 8002490:	1889      	adds	r1, r1, r2
 8002492:	0c09      	lsrs	r1, r1, #16
 8002494:	2220      	movs	r2, #32
 8002496:	f06e fafb 	bl	0x8070a90
 800249a:	bc01      	pop	{r0}
 800249c:	4700      	bx	r0
 800249e:	0000      	movs	r0, r0
 80024a0:	b510      	push	{r4, lr}
 80024a2:	0400      	lsls	r0, r0, #16
 80024a4:	0c04      	lsrs	r4, r0, #16
 80024a6:	4806      	ldr	r0, [pc, #24]	@ (0x80024c0)
 80024a8:	f000 f812 	bl	0x80024d0
 80024ac:	0600      	lsls	r0, r0, #24
 80024ae:	0e02      	lsrs	r2, r0, #24
 80024b0:	2aff      	cmp	r2, #255	@ 0xff
 80024b2:	d009      	beq.n	0x80024c8
 80024b4:	4903      	ldr	r1, [pc, #12]	@ (0x80024c4)
 80024b6:	0050      	lsls	r0, r2, #1
 80024b8:	1840      	adds	r0, r0, r1
 80024ba:	8004      	strh	r4, [r0, #0]
 80024bc:	1c10      	adds	r0, r2, #0
 80024be:	e004      	b.n	0x80024ca
 80024c0:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 80024c4:	0300      	lsls	r0, r0, #12
 80024c6:	0300      	lsls	r0, r0, #12
 80024c8:	20ff      	movs	r0, #255	@ 0xff
 80024ca:	bc10      	pop	{r4}
 80024cc:	bc02      	pop	{r1}
 80024ce:	4708      	bx	r1
 80024d0:	b500      	push	{lr}
 80024d2:	0400      	lsls	r0, r0, #16
 80024d4:	0c02      	lsrs	r2, r0, #16
 80024d6:	4806      	ldr	r0, [pc, #24]	@ (0x80024f0)
 80024d8:	7801      	ldrb	r1, [r0, #0]
 80024da:	290f      	cmp	r1, #15
 80024dc:	d811      	bhi.n	0x8002502
 80024de:	4b05      	ldr	r3, [pc, #20]	@ (0x80024f4)
 80024e0:	0048      	lsls	r0, r1, #1
 80024e2:	18c0      	adds	r0, r0, r3
 80024e4:	8800      	ldrh	r0, [r0, #0]
 80024e6:	4290      	cmp	r0, r2
 80024e8:	d106      	bne.n	0x80024f8
 80024ea:	1c08      	adds	r0, r1, #0
 80024ec:	e00a      	b.n	0x8002504
 80024ee:	0000      	movs	r0, r0
 80024f0:	2868      	cmp	r0, #104	@ 0x68
 80024f2:	0300      	lsls	r0, r0, #12
 80024f4:	0300      	lsls	r0, r0, #12
 80024f6:	0300      	lsls	r0, r0, #12
 80024f8:	1c48      	adds	r0, r1, #1
 80024fa:	0600      	lsls	r0, r0, #24
 80024fc:	0e01      	lsrs	r1, r0, #24
 80024fe:	290f      	cmp	r1, #15
 8002500:	d9ee      	bls.n	0x80024e0
 8002502:	20ff      	movs	r0, #255	@ 0xff
 8002504:	bc02      	pop	{r1}
 8002506:	4708      	bx	r1
 8002508:	0600      	lsls	r0, r0, #24
 800250a:	4902      	ldr	r1, [pc, #8]	@ (0x8002514)
 800250c:	0dc0      	lsrs	r0, r0, #23
 800250e:	1840      	adds	r0, r0, r1
 8002510:	8800      	ldrh	r0, [r0, #0]
 8002512:	4770      	bx	lr
 8002514:	0300      	lsls	r0, r0, #12
 8002516:	0300      	lsls	r0, r0, #12
 8002518:	b500      	push	{lr}
 800251a:	0400      	lsls	r0, r0, #16
 800251c:	0c00      	lsrs	r0, r0, #16
 800251e:	f7ff ffd7 	bl	0x80024d0
 8002522:	0600      	lsls	r0, r0, #24
 8002524:	0e01      	lsrs	r1, r0, #24
 8002526:	29ff      	cmp	r1, #255	@ 0xff
 8002528:	d004      	beq.n	0x8002534
 800252a:	4803      	ldr	r0, [pc, #12]	@ (0x8002538)
 800252c:	0049      	lsls	r1, r1, #1
 800252e:	1809      	adds	r1, r1, r0
 8002530:	4802      	ldr	r0, [pc, #8]	@ (0x800253c)
 8002532:	8008      	strh	r0, [r1, #0]
 8002534:	bc01      	pop	{r0}
 8002536:	4700      	bx	r0
 8002538:	0300      	lsls	r0, r0, #12
 800253a:	0300      	lsls	r0, r0, #12
 800253c:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 8002540:	6181      	str	r1, [r0, #24]
 8002542:	3042      	adds	r0, #66	@ 0x42
 8002544:	2140      	movs	r1, #64	@ 0x40
 8002546:	7001      	strb	r1, [r0, #0]
 8002548:	4770      	bx	lr
 800254a:	0000      	movs	r0, r0
 800254c:	b510      	push	{r4, lr}
 800254e:	1c04      	adds	r4, r0, #0
 8002550:	1c0b      	adds	r3, r1, #0
 8002552:	4903      	ldr	r1, [pc, #12]	@ (0x8002560)
 8002554:	7818      	ldrb	r0, [r3, #0]
 8002556:	7809      	ldrb	r1, [r1, #0]
 8002558:	4288      	cmp	r0, r1
 800255a:	d303      	bcc.n	0x8002564
 800255c:	2001      	movs	r0, #1
 800255e:	e025      	b.n	0x80025ac
 8002560:	2444      	movs	r4, #68	@ 0x44
 8002562:	0300      	lsls	r0, r0, #12
 8002564:	69a0      	ldr	r0, [r4, #24]
 8002566:	2800      	cmp	r0, #0
 8002568:	d006      	beq.n	0x8002578
 800256a:	1c20      	adds	r0, r4, #0
 800256c:	3042      	adds	r0, #66	@ 0x42
 800256e:	7801      	ldrb	r1, [r0, #0]
 8002570:	20c0      	movs	r0, #192	@ 0xc0
 8002572:	4008      	ands	r0, r1
 8002574:	2800      	cmp	r0, #0
 8002576:	d10f      	bne.n	0x8002598
 8002578:	4806      	ldr	r0, [pc, #24]	@ (0x8002594)
 800257a:	781a      	ldrb	r2, [r3, #0]
 800257c:	00d2      	lsls	r2, r2, #3
 800257e:	3038      	adds	r0, #56	@ 0x38
 8002580:	1812      	adds	r2, r2, r0
 8002582:	6820      	ldr	r0, [r4, #0]
 8002584:	6861      	ldr	r1, [r4, #4]
 8002586:	6010      	str	r0, [r2, #0]
 8002588:	6051      	str	r1, [r2, #4]
 800258a:	7818      	ldrb	r0, [r3, #0]
 800258c:	3001      	adds	r0, #1
 800258e:	7018      	strb	r0, [r3, #0]
 8002590:	2000      	movs	r0, #0
 8002592:	e00b      	b.n	0x80025ac
 8002594:	16e0      	asrs	r0, r4, #27
 8002596:	0300      	lsls	r0, r0, #12
 8002598:	7819      	ldrb	r1, [r3, #0]
 800259a:	00c9      	lsls	r1, r1, #3
 800259c:	4805      	ldr	r0, [pc, #20]	@ (0x80025b4)
 800259e:	1809      	adds	r1, r1, r0
 80025a0:	1c20      	adds	r0, r4, #0
 80025a2:	1c1a      	adds	r2, r3, #0
 80025a4:	f000 f808 	bl	0x80025b8
 80025a8:	0600      	lsls	r0, r0, #24
 80025aa:	0e00      	lsrs	r0, r0, #24
 80025ac:	bc10      	pop	{r4}
 80025ae:	bc02      	pop	{r1}
 80025b0:	4708      	bx	r1
 80025b2:	0000      	movs	r0, r0
 80025b4:	1718      	asrs	r0, r3, #28
 80025b6:	0300      	lsls	r0, r0, #12
 80025b8:	b5f0      	push	{r4, r5, r6, r7, lr}
 80025ba:	4657      	mov	r7, sl
 80025bc:	464e      	mov	r6, r9
 80025be:	4645      	mov	r5, r8
 80025c0:	b4e0      	push	{r5, r6, r7}
 80025c2:	b087      	sub	sp, #28
 80025c4:	1c03      	adds	r3, r0, #0
 80025c6:	9100      	str	r1, [sp, #0]
 80025c8:	4690      	mov	r8, r2
 80025ca:	4803      	ldr	r0, [pc, #12]	@ (0x80025d8)
 80025cc:	7811      	ldrb	r1, [r2, #0]
 80025ce:	7800      	ldrb	r0, [r0, #0]
 80025d0:	4281      	cmp	r1, r0
 80025d2:	d303      	bcc.n	0x80025dc
 80025d4:	2001      	movs	r0, #1
 80025d6:	e0ec      	b.n	0x80027b2
 80025d8:	2444      	movs	r4, #68	@ 0x44
 80025da:	0300      	lsls	r0, r0, #12
 80025dc:	1c18      	adds	r0, r3, #0
 80025de:	3042      	adds	r0, #66	@ 0x42
 80025e0:	7801      	ldrb	r1, [r0, #0]
 80025e2:	0689      	lsls	r1, r1, #26
 80025e4:	0dc9      	lsrs	r1, r1, #23
 80025e6:	699a      	ldr	r2, [r3, #24]
 80025e8:	1857      	adds	r7, r2, r1
 80025ea:	469c      	mov	ip, r3
 80025ec:	9006      	str	r0, [sp, #24]
 80025ee:	2f00      	cmp	r7, #0
 80025f0:	d002      	beq.n	0x80025f8
 80025f2:	6878      	ldr	r0, [r7, #4]
 80025f4:	2800      	cmp	r0, #0
 80025f6:	d10a      	bne.n	0x800260e
 80025f8:	4662      	mov	r2, ip
 80025fa:	6810      	ldr	r0, [r2, #0]
 80025fc:	6851      	ldr	r1, [r2, #4]
 80025fe:	9a00      	ldr	r2, [sp, #0]
 8002600:	6010      	str	r0, [r2, #0]
 8002602:	6051      	str	r1, [r2, #4]
 8002604:	4641      	mov	r1, r8
 8002606:	7808      	ldrb	r0, [r1, #0]
 8002608:	3001      	adds	r0, #1
 800260a:	7008      	strb	r0, [r1, #0]
 800260c:	e0d0      	b.n	0x80027b0
 800260e:	4662      	mov	r2, ip
 8002610:	8890      	ldrh	r0, [r2, #4]
 8002612:	0580      	lsls	r0, r0, #22
 8002614:	0d80      	lsrs	r0, r0, #22
 8002616:	9001      	str	r0, [sp, #4]
 8002618:	7838      	ldrb	r0, [r7, #0]
 800261a:	9003      	str	r0, [sp, #12]
 800261c:	78d0      	ldrb	r0, [r2, #3]
 800261e:	0680      	lsls	r0, r0, #26
 8002620:	0ec0      	lsrs	r0, r0, #27
 8002622:	10c1      	asrs	r1, r0, #3
 8002624:	9104      	str	r1, [sp, #16]
 8002626:	2101      	movs	r1, #1
 8002628:	9a04      	ldr	r2, [sp, #16]
 800262a:	400a      	ands	r2, r1
 800262c:	9204      	str	r2, [sp, #16]
 800262e:	1100      	asrs	r0, r0, #4
 8002630:	4682      	mov	sl, r0
 8002632:	4008      	ands	r0, r1
 8002634:	4682      	mov	sl, r0
 8002636:	4661      	mov	r1, ip
 8002638:	8848      	ldrh	r0, [r1, #2]
 800263a:	05c0      	lsls	r0, r0, #23
 800263c:	0dc0      	lsrs	r0, r0, #23
 800263e:	3128      	adds	r1, #40	@ 0x28
 8002640:	7809      	ldrb	r1, [r1, #0]
 8002642:	0609      	lsls	r1, r1, #24
 8002644:	1609      	asrs	r1, r1, #24
 8002646:	1a40      	subs	r0, r0, r1
 8002648:	0400      	lsls	r0, r0, #16
 800264a:	0c02      	lsrs	r2, r0, #16
 800264c:	4661      	mov	r1, ip
 800264e:	7808      	ldrb	r0, [r1, #0]
 8002650:	3129      	adds	r1, #41	@ 0x29
 8002652:	7809      	ldrb	r1, [r1, #0]
 8002654:	0609      	lsls	r1, r1, #24
 8002656:	1609      	asrs	r1, r1, #24
 8002658:	1a40      	subs	r0, r0, r1
 800265a:	0400      	lsls	r0, r0, #16
 800265c:	0c00      	lsrs	r0, r0, #16
 800265e:	9002      	str	r0, [sp, #8]
 8002660:	2000      	movs	r0, #0
 8002662:	4681      	mov	r9, r0
 8002664:	9903      	ldr	r1, [sp, #12]
 8002666:	4589      	cmp	r9, r1
 8002668:	d300      	bcc.n	0x800266c
 800266a:	e0a1      	b.n	0x80027b0
 800266c:	0410      	lsls	r0, r2, #16
 800266e:	1400      	asrs	r0, r0, #16
 8002670:	9005      	str	r0, [sp, #20]
 8002672:	4642      	mov	r2, r8
 8002674:	7810      	ldrb	r0, [r2, #0]
 8002676:	4953      	ldr	r1, [pc, #332]	@ (0x80027c4)
 8002678:	7809      	ldrb	r1, [r1, #0]
 800267a:	4288      	cmp	r0, r1
 800267c:	d2aa      	bcs.n	0x80025d4
 800267e:	6878      	ldr	r0, [r7, #4]
 8002680:	464a      	mov	r2, r9
 8002682:	0096      	lsls	r6, r2, #2
 8002684:	1832      	adds	r2, r6, r0
 8002686:	2000      	movs	r0, #0
 8002688:	5610      	ldrsb	r0, [r2, r0]
 800268a:	0400      	lsls	r0, r0, #16
 800268c:	0c04      	lsrs	r4, r0, #16
 800268e:	2001      	movs	r0, #1
 8002690:	5610      	ldrsb	r0, [r2, r0]
 8002692:	0400      	lsls	r0, r0, #16
 8002694:	0c05      	lsrs	r5, r0, #16
 8002696:	9804      	ldr	r0, [sp, #16]
 8002698:	2800      	cmp	r0, #0
 800269a:	d015      	beq.n	0x80026c8
 800269c:	6810      	ldr	r0, [r2, #0]
 800269e:	0301      	lsls	r1, r0, #12
 80026a0:	0f89      	lsrs	r1, r1, #30
 80026a2:	0089      	lsls	r1, r1, #2
 80026a4:	0380      	lsls	r0, r0, #14
 80026a6:	0f80      	lsrs	r0, r0, #30
 80026a8:	0100      	lsls	r0, r0, #4
 80026aa:	1809      	adds	r1, r1, r0
 80026ac:	4846      	ldr	r0, [pc, #280]	@ (0x80027c8)
 80026ae:	1809      	adds	r1, r1, r0
 80026b0:	7809      	ldrb	r1, [r1, #0]
 80026b2:	0609      	lsls	r1, r1, #24
 80026b4:	1609      	asrs	r1, r1, #24
 80026b6:	0420      	lsls	r0, r4, #16
 80026b8:	1400      	asrs	r0, r0, #16
 80026ba:	1840      	adds	r0, r0, r1
 80026bc:	0400      	lsls	r0, r0, #16
 80026be:	0c04      	lsrs	r4, r0, #16
 80026c0:	43e0      	mvns	r0, r4
 80026c2:	3001      	adds	r0, #1
 80026c4:	0400      	lsls	r0, r0, #16
 80026c6:	0c04      	lsrs	r4, r0, #16
 80026c8:	4651      	mov	r1, sl
 80026ca:	2900      	cmp	r1, #0
 80026cc:	d015      	beq.n	0x80026fa
 80026ce:	6810      	ldr	r0, [r2, #0]
 80026d0:	0301      	lsls	r1, r0, #12
 80026d2:	0f89      	lsrs	r1, r1, #30
 80026d4:	0089      	lsls	r1, r1, #2
 80026d6:	0380      	lsls	r0, r0, #14
 80026d8:	0f80      	lsrs	r0, r0, #30
 80026da:	0100      	lsls	r0, r0, #4
 80026dc:	1809      	adds	r1, r1, r0
 80026de:	4a3a      	ldr	r2, [pc, #232]	@ (0x80027c8)
 80026e0:	1889      	adds	r1, r1, r2
 80026e2:	7849      	ldrb	r1, [r1, #1]
 80026e4:	0609      	lsls	r1, r1, #24
 80026e6:	1609      	asrs	r1, r1, #24
 80026e8:	0428      	lsls	r0, r5, #16
 80026ea:	1400      	asrs	r0, r0, #16
 80026ec:	1840      	adds	r0, r0, r1
 80026ee:	0400      	lsls	r0, r0, #16
 80026f0:	0c05      	lsrs	r5, r0, #16
 80026f2:	43e8      	mvns	r0, r5
 80026f4:	3001      	adds	r0, #1
 80026f6:	0400      	lsls	r0, r0, #16
 80026f8:	0c05      	lsrs	r5, r0, #16
 80026fa:	4649      	mov	r1, r9
 80026fc:	00c8      	lsls	r0, r1, #3
 80026fe:	9a00      	ldr	r2, [sp, #0]
 8002700:	1883      	adds	r3, r0, r2
 8002702:	4662      	mov	r2, ip
 8002704:	6810      	ldr	r0, [r2, #0]
 8002706:	6851      	ldr	r1, [r2, #4]
 8002708:	6018      	str	r0, [r3, #0]
 800270a:	6059      	str	r1, [r3, #4]
 800270c:	6878      	ldr	r0, [r7, #4]
 800270e:	1830      	adds	r0, r6, r0
 8002710:	6801      	ldr	r1, [r0, #0]
 8002712:	0389      	lsls	r1, r1, #14
 8002714:	0f89      	lsrs	r1, r1, #30
 8002716:	0189      	lsls	r1, r1, #6
 8002718:	785a      	ldrb	r2, [r3, #1]
 800271a:	203f      	movs	r0, #63	@ 0x3f
 800271c:	4010      	ands	r0, r2
 800271e:	4308      	orrs	r0, r1
 8002720:	7058      	strb	r0, [r3, #1]
 8002722:	6878      	ldr	r0, [r7, #4]
 8002724:	1830      	adds	r0, r6, r0
 8002726:	6801      	ldr	r1, [r0, #0]
 8002728:	0309      	lsls	r1, r1, #12
 800272a:	0f89      	lsrs	r1, r1, #30
 800272c:	0189      	lsls	r1, r1, #6
 800272e:	78da      	ldrb	r2, [r3, #3]
 8002730:	203f      	movs	r0, #63	@ 0x3f
 8002732:	4010      	ands	r0, r2
 8002734:	4308      	orrs	r0, r1
 8002736:	70d8      	strb	r0, [r3, #3]
 8002738:	0421      	lsls	r1, r4, #16
 800273a:	1409      	asrs	r1, r1, #16
 800273c:	9805      	ldr	r0, [sp, #20]
 800273e:	1841      	adds	r1, r0, r1
 8002740:	4a22      	ldr	r2, [pc, #136]	@ (0x80027cc)
 8002742:	1c10      	adds	r0, r2, #0
 8002744:	4001      	ands	r1, r0
 8002746:	885a      	ldrh	r2, [r3, #2]
 8002748:	4821      	ldr	r0, [pc, #132]	@ (0x80027d0)
 800274a:	4010      	ands	r0, r2
 800274c:	4308      	orrs	r0, r1
 800274e:	8058      	strh	r0, [r3, #2]
 8002750:	9902      	ldr	r1, [sp, #8]
 8002752:	1948      	adds	r0, r1, r5
 8002754:	7018      	strb	r0, [r3, #0]
 8002756:	6878      	ldr	r0, [r7, #4]
 8002758:	1830      	adds	r0, r6, r0
 800275a:	6801      	ldr	r1, [r0, #0]
 800275c:	0089      	lsls	r1, r1, #2
 800275e:	0d89      	lsrs	r1, r1, #22
 8002760:	9a01      	ldr	r2, [sp, #4]
 8002762:	1851      	adds	r1, r2, r1
 8002764:	4a1b      	ldr	r2, [pc, #108]	@ (0x80027d4)
 8002766:	1c10      	adds	r0, r2, #0
 8002768:	4001      	ands	r1, r0
 800276a:	889a      	ldrh	r2, [r3, #4]
 800276c:	481a      	ldr	r0, [pc, #104]	@ (0x80027d8)
 800276e:	4010      	ands	r0, r2
 8002770:	4308      	orrs	r0, r1
 8002772:	8098      	strh	r0, [r3, #4]
 8002774:	9806      	ldr	r0, [sp, #24]
 8002776:	7801      	ldrb	r1, [r0, #0]
 8002778:	20c0      	movs	r0, #192	@ 0xc0
 800277a:	4008      	ands	r0, r1
 800277c:	2880      	cmp	r0, #128	@ 0x80
 800277e:	d00a      	beq.n	0x8002796
 8002780:	6878      	ldr	r0, [r7, #4]
 8002782:	1830      	adds	r0, r6, r0
 8002784:	6801      	ldr	r1, [r0, #0]
 8002786:	0f89      	lsrs	r1, r1, #30
 8002788:	0089      	lsls	r1, r1, #2
 800278a:	795a      	ldrb	r2, [r3, #5]
 800278c:	200d      	movs	r0, #13
 800278e:	4240      	negs	r0, r0
 8002790:	4010      	ands	r0, r2
 8002792:	4308      	orrs	r0, r1
 8002794:	7158      	strb	r0, [r3, #5]
 8002796:	4648      	mov	r0, r9
 8002798:	3001      	adds	r0, #1
 800279a:	0600      	lsls	r0, r0, #24
 800279c:	0e00      	lsrs	r0, r0, #24
 800279e:	4681      	mov	r9, r0
 80027a0:	4641      	mov	r1, r8
 80027a2:	7808      	ldrb	r0, [r1, #0]
 80027a4:	3001      	adds	r0, #1
 80027a6:	7008      	strb	r0, [r1, #0]
 80027a8:	9a03      	ldr	r2, [sp, #12]
 80027aa:	4591      	cmp	r9, r2
 80027ac:	d200      	bcs.n	0x80027b0
 80027ae:	e760      	b.n	0x8002672
 80027b0:	2000      	movs	r0, #0
 80027b2:	b007      	add	sp, #28
 80027b4:	bc38      	pop	{r3, r4, r5}
 80027b6:	4698      	mov	r8, r3
 80027b8:	46a1      	mov	r9, r4
 80027ba:	46aa      	mov	sl, r5
 80027bc:	bcf0      	pop	{r4, r5, r6, r7}
 80027be:	bc02      	pop	{r1}
 80027c0:	4708      	bx	r1
 80027c2:	0000      	movs	r0, r0
 80027c4:	2444      	movs	r4, #68	@ 0x44
 80027c6:	0300      	lsls	r0, r0, #12
 80027c8:	3404      	adds	r4, #4
 80027ca:	081b      	lsrs	r3, r3, #32
 80027cc:	01ff      	lsls	r7, r7, #7
 80027ce:	0000      	movs	r0, r0
 80027d0:	fe00 ffff 			@ <UNDEFINED> instruction: 0xfe00ffff
 80027d4:	03ff      	lsls	r7, r7, #15
 80027d6:	0000      	movs	r0, r0
 80027d8:	fc00 ffff 			@ <UNDEFINED> instruction: 0xfc00ffff
 80027dc:	b510      	push	{r4, lr}
 80027de:	4c07      	ldr	r4, [pc, #28]	@ (0x80027fc)
 80027e0:	f001 fd22 	bl	0x8004228
 80027e4:	6020      	str	r0, [r4, #0]
 80027e6:	f000 f847 	bl	0x8002878
 80027ea:	6820      	ldr	r0, [r4, #0]
 80027ec:	f000 f820 	bl	0x8002830
 80027f0:	6820      	ldr	r0, [r4, #0]
 80027f2:	f000 f835 	bl	0x8002860
 80027f6:	bc10      	pop	{r4}
 80027f8:	bc01      	pop	{r0}
 80027fa:	4700      	bx	r0
 80027fc:	0320      	lsls	r0, r4, #12
 80027fe:	0300      	lsls	r0, r0, #12
 8002800:	b500      	push	{lr}
 8002802:	f001 fd11 	bl	0x8004228
 8002806:	f000 f813 	bl	0x8002830
 800280a:	bc01      	pop	{r0}
 800280c:	4700      	bx	r0
 800280e:	0000      	movs	r0, r0
 8002810:	b500      	push	{lr}
 8002812:	f001 fd09 	bl	0x8004228
 8002816:	f000 f823 	bl	0x8002860
 800281a:	bc01      	pop	{r0}
 800281c:	4700      	bx	r0
 800281e:	0000      	movs	r0, r0
 8002820:	b500      	push	{lr}
 8002822:	f001 fd01 	bl	0x8004228
 8002826:	f000 f827 	bl	0x8002878
 800282a:	bc01      	pop	{r0}
 800282c:	4700      	bx	r0
 800282e:	0000      	movs	r0, r0
 8002830:	b530      	push	{r4, r5, lr}
 8002832:	b082      	sub	sp, #8
 8002834:	1c05      	adds	r5, r0, #0
 8002836:	2400      	movs	r4, #0
 8002838:	9400      	str	r4, [sp, #0]
 800283a:	68e9      	ldr	r1, [r5, #12]
 800283c:	4a06      	ldr	r2, [pc, #24]	@ (0x8002858)
 800283e:	4668      	mov	r0, sp
 8002840:	f1ae fd26 	bl	0x81b1290
 8002844:	9401      	str	r4, [sp, #4]
 8002846:	a801      	add	r0, sp, #4
 8002848:	6929      	ldr	r1, [r5, #16]
 800284a:	4a04      	ldr	r2, [pc, #16]	@ (0x800285c)
 800284c:	f1ae fd20 	bl	0x81b1290
 8002850:	b002      	add	sp, #8
 8002852:	bc30      	pop	{r4, r5}
 8002854:	bc01      	pop	{r0}
 8002856:	4700      	bx	r0
 8002858:	0008      	movs	r0, r1
 800285a:	0100      	lsls	r0, r0, #4
 800285c:	0200      	lsls	r0, r0, #8
 800285e:	0100      	lsls	r0, r0, #4
 8002860:	b500      	push	{lr}
 8002862:	4a04      	ldr	r2, [pc, #16]	@ (0x8002874)
 8002864:	7901      	ldrb	r1, [r0, #4]
 8002866:	0109      	lsls	r1, r1, #4
 8002868:	1c10      	adds	r0, r2, #0
 800286a:	2220      	movs	r2, #32
 800286c:	f06e f910 	bl	0x8070a90
 8002870:	bc01      	pop	{r0}
 8002872:	4700      	bx	r0
 8002874:	3a8c      	subs	r2, #140	@ 0x8c
 8002876:	081b      	lsrs	r3, r3, #32
 8002878:	4a0d      	ldr	r2, [pc, #52]	@ (0x80028b0)
 800287a:	7801      	ldrb	r1, [r0, #0]
 800287c:	0089      	lsls	r1, r1, #2
 800287e:	1889      	adds	r1, r1, r2
 8002880:	6809      	ldr	r1, [r1, #0]
 8002882:	2300      	movs	r3, #0
 8002884:	800b      	strh	r3, [r1, #0]
 8002886:	4a0b      	ldr	r2, [pc, #44]	@ (0x80028b4)
 8002888:	7801      	ldrb	r1, [r0, #0]
 800288a:	0089      	lsls	r1, r1, #2
 800288c:	1889      	adds	r1, r1, r2
 800288e:	6809      	ldr	r1, [r1, #0]
 8002890:	800b      	strh	r3, [r1, #0]
 8002892:	4a09      	ldr	r2, [pc, #36]	@ (0x80028b8)
 8002894:	7801      	ldrb	r1, [r0, #0]
 8002896:	0089      	lsls	r1, r1, #2
 8002898:	1889      	adds	r1, r1, r2
 800289a:	680b      	ldr	r3, [r1, #0]
 800289c:	78c2      	ldrb	r2, [r0, #3]
 800289e:	7881      	ldrb	r1, [r0, #2]
 80028a0:	0209      	lsls	r1, r1, #8
 80028a2:	430a      	orrs	r2, r1
 80028a4:	7840      	ldrb	r0, [r0, #1]
 80028a6:	0080      	lsls	r0, r0, #2
 80028a8:	4302      	orrs	r2, r0
 80028aa:	801a      	strh	r2, [r3, #0]
 80028ac:	4770      	bx	lr
 80028ae:	0000      	movs	r0, r0
 80028b0:	344c      	adds	r4, #76	@ 0x4c
 80028b2:	081b      	lsrs	r3, r3, #32
 80028b4:	345c      	adds	r4, #92	@ 0x5c
 80028b6:	081b      	lsrs	r3, r3, #32
 80028b8:	343c      	adds	r4, #60	@ 0x3c
 80028ba:	081b      	lsrs	r3, r3, #32
 80028bc:	b500      	push	{lr}
 80028be:	1c02      	adds	r2, r0, #0
 80028c0:	0409      	lsls	r1, r1, #16
 80028c2:	0c0b      	lsrs	r3, r1, #16
 80028c4:	82d3      	strh	r3, [r2, #22]
 80028c6:	6810      	ldr	r0, [r2, #0]
 80028c8:	7a40      	ldrb	r0, [r0, #9]
 80028ca:	2801      	cmp	r0, #1
 80028cc:	d00c      	beq.n	0x80028e8
 80028ce:	2801      	cmp	r0, #1
 80028d0:	dd08      	ble.n	0x80028e4
 80028d2:	2802      	cmp	r0, #2
 80028d4:	d038      	beq.n	0x8002948
 80028d6:	2803      	cmp	r0, #3
 80028d8:	d106      	bne.n	0x80028e8
 80028da:	1c10      	adds	r0, r2, #0
 80028dc:	1c19      	adds	r1, r3, #0
 80028de:	f000 f977 	bl	0x8002bd0
 80028e2:	e02e      	b.n	0x8002942
 80028e4:	2800      	cmp	r0, #0
 80028e6:	d02f      	beq.n	0x8002948
 80028e8:	6810      	ldr	r0, [r2, #0]
 80028ea:	7a01      	ldrb	r1, [r0, #8]
 80028ec:	1c02      	adds	r2, r0, #0
 80028ee:	2906      	cmp	r1, #6
 80028f0:	d82a      	bhi.n	0x8002948
 80028f2:	0088      	lsls	r0, r1, #2
 80028f4:	4901      	ldr	r1, [pc, #4]	@ (0x80028fc)
 80028f6:	1840      	adds	r0, r0, r1
 80028f8:	6800      	ldr	r0, [r0, #0]
 80028fa:	4687      	mov	pc, r0
 80028fc:	2900      	cmp	r1, #0
 80028fe:	0800      	lsrs	r0, r0, #32
 8002900:	291c      	cmp	r1, #28
 8002902:	0800      	lsrs	r0, r0, #32
 8002904:	2926      	cmp	r1, #38	@ 0x26
 8002906:	0800      	lsrs	r0, r0, #32
 8002908:	2926      	cmp	r1, #38	@ 0x26
 800290a:	0800      	lsrs	r0, r0, #32
 800290c:	291c      	cmp	r1, #28
 800290e:	0800      	lsrs	r0, r0, #32
 8002910:	2930      	cmp	r1, #48	@ 0x30
 8002912:	0800      	lsrs	r0, r0, #32
 8002914:	2930      	cmp	r1, #48	@ 0x30
 8002916:	0800      	lsrs	r0, r0, #32
 8002918:	293a      	cmp	r1, #58	@ 0x3a
 800291a:	0800      	lsrs	r0, r0, #32
 800291c:	1c10      	adds	r0, r2, #0
 800291e:	1c19      	adds	r1, r3, #0
 8002920:	f000 f8e8 	bl	0x8002af4
 8002924:	e00d      	b.n	0x8002942
 8002926:	1c10      	adds	r0, r2, #0
 8002928:	1c19      	adds	r1, r3, #0
 800292a:	f000 f8ff 	bl	0x8002b2c
 800292e:	e008      	b.n	0x8002942
 8002930:	1c10      	adds	r0, r2, #0
 8002932:	1c19      	adds	r1, r3, #0
 8002934:	f000 f914 	bl	0x8002b60
 8002938:	e003      	b.n	0x8002942
 800293a:	1c10      	adds	r0, r2, #0
 800293c:	1c19      	adds	r1, r3, #0
 800293e:	f000 f92d 	bl	0x8002b9c
 8002942:	0400      	lsls	r0, r0, #16
 8002944:	0c00      	lsrs	r0, r0, #16
 8002946:	e000      	b.n	0x800294a
 8002948:	2000      	movs	r0, #0
 800294a:	bc02      	pop	{r1}
 800294c:	4708      	bx	r1
 800294e:	0000      	movs	r0, r0
 8002950:	b500      	push	{lr}
 8002952:	1c03      	adds	r3, r0, #0
 8002954:	0409      	lsls	r1, r1, #16
 8002956:	0c09      	lsrs	r1, r1, #16
 8002958:	1c0a      	adds	r2, r1, #0
 800295a:	490c      	ldr	r1, [pc, #48]	@ (0x800298c)
 800295c:	2000      	movs	r0, #0
 800295e:	8008      	strh	r0, [r1, #0]
 8002960:	480b      	ldr	r0, [pc, #44]	@ (0x8002990)
 8002962:	6819      	ldr	r1, [r3, #0]
 8002964:	6001      	str	r1, [r0, #0]
 8002966:	480b      	ldr	r0, [pc, #44]	@ (0x8002994)
 8002968:	8002      	strh	r2, [r0, #0]
 800296a:	82da      	strh	r2, [r3, #22]
 800296c:	7a48      	ldrb	r0, [r1, #9]
 800296e:	2801      	cmp	r0, #1
 8002970:	d014      	beq.n	0x800299c
 8002972:	2801      	cmp	r0, #1
 8002974:	dd10      	ble.n	0x8002998
 8002976:	2802      	cmp	r0, #2
 8002978:	d02e      	beq.n	0x80029d8
 800297a:	2803      	cmp	r0, #3
 800297c:	d10e      	bne.n	0x800299c
 800297e:	1c18      	adds	r0, r3, #0
 8002980:	1c11      	adds	r1, r2, #0
 8002982:	f000 f925 	bl	0x8002bd0
 8002986:	0400      	lsls	r0, r0, #16
 8002988:	0c00      	lsrs	r0, r0, #16
 800298a:	e026      	b.n	0x80029da
 800298c:	032e      	lsls	r6, r5, #12
 800298e:	0300      	lsls	r0, r0, #12
 8002990:	0328      	lsls	r0, r5, #12
 8002992:	0300      	lsls	r0, r0, #12
 8002994:	032c      	lsls	r4, r5, #12
 8002996:	0300      	lsls	r0, r0, #12
 8002998:	2800      	cmp	r0, #0
 800299a:	d01d      	beq.n	0x80029d8
 800299c:	6818      	ldr	r0, [r3, #0]
 800299e:	7a00      	ldrb	r0, [r0, #8]
 80029a0:	2805      	cmp	r0, #5
 80029a2:	d819      	bhi.n	0x80029d8
 80029a4:	0080      	lsls	r0, r0, #2
 80029a6:	4902      	ldr	r1, [pc, #8]	@ (0x80029b0)
 80029a8:	1840      	adds	r0, r0, r1
 80029aa:	6800      	ldr	r0, [r0, #0]
 80029ac:	4687      	mov	pc, r0
 80029ae:	0000      	movs	r0, r0
 80029b0:	29b4      	cmp	r1, #180	@ 0xb4
 80029b2:	0800      	lsrs	r0, r0, #32
 80029b4:	29cc      	cmp	r1, #204	@ 0xcc
 80029b6:	0800      	lsrs	r0, r0, #32
 80029b8:	29d2      	cmp	r1, #210	@ 0xd2
 80029ba:	0800      	lsrs	r0, r0, #32
 80029bc:	29d2      	cmp	r1, #210	@ 0xd2
 80029be:	0800      	lsrs	r0, r0, #32
 80029c0:	29cc      	cmp	r1, #204	@ 0xcc
 80029c2:	0800      	lsrs	r0, r0, #32
 80029c4:	29d2      	cmp	r1, #210	@ 0xd2
 80029c6:	0800      	lsrs	r0, r0, #32
 80029c8:	29d2      	cmp	r1, #210	@ 0xd2
 80029ca:	0800      	lsrs	r0, r0, #32
 80029cc:	2080      	movs	r0, #128	@ 0x80
 80029ce:	0080      	lsls	r0, r0, #2
 80029d0:	e003      	b.n	0x80029da
 80029d2:	2080      	movs	r0, #128	@ 0x80
 80029d4:	0040      	lsls	r0, r0, #1
 80029d6:	e000      	b.n	0x80029da
 80029d8:	2000      	movs	r0, #0
 80029da:	bc02      	pop	{r1}
 80029dc:	4708      	bx	r1
 80029de:	0000      	movs	r0, r0
 80029e0:	b510      	push	{r4, lr}
 80029e2:	4807      	ldr	r0, [pc, #28]	@ (0x8002a00)
 80029e4:	6800      	ldr	r0, [r0, #0]
 80029e6:	7a40      	ldrb	r0, [r0, #9]
 80029e8:	2800      	cmp	r0, #0
 80029ea:	d02d      	beq.n	0x8002a48
 80029ec:	2800      	cmp	r0, #0
 80029ee:	db03      	blt.n	0x80029f8
 80029f0:	2803      	cmp	r0, #3
 80029f2:	dc01      	bgt.n	0x80029f8
 80029f4:	2802      	cmp	r0, #2
 80029f6:	da27      	bge.n	0x8002a48
 80029f8:	4802      	ldr	r0, [pc, #8]	@ (0x8002a04)
 80029fa:	8804      	ldrh	r4, [r0, #0]
 80029fc:	1c20      	adds	r0, r4, #0
 80029fe:	e00e      	b.n	0x8002a1e
 8002a00:	0328      	lsls	r0, r5, #12
 8002a02:	0300      	lsls	r0, r0, #12
 8002a04:	032e      	lsls	r6, r5, #12
 8002a06:	0300      	lsls	r0, r0, #12
 8002a08:	480c      	ldr	r0, [pc, #48]	@ (0x8002a3c)
 8002a0a:	6800      	ldr	r0, [r0, #0]
 8002a0c:	490c      	ldr	r1, [pc, #48]	@ (0x8002a40)
 8002a0e:	8809      	ldrh	r1, [r1, #0]
 8002a10:	0622      	lsls	r2, r4, #24
 8002a12:	0e12      	lsrs	r2, r2, #24
 8002a14:	f000 f81c 	bl	0x8002a50
 8002a18:	3401      	adds	r4, #1
 8002a1a:	480a      	ldr	r0, [pc, #40]	@ (0x8002a44)
 8002a1c:	8800      	ldrh	r0, [r0, #0]
 8002a1e:	3010      	adds	r0, #16
 8002a20:	4284      	cmp	r4, r0
 8002a22:	dbf1      	blt.n	0x8002a08
 8002a24:	4807      	ldr	r0, [pc, #28]	@ (0x8002a44)
 8002a26:	8801      	ldrh	r1, [r0, #0]
 8002a28:	3110      	adds	r1, #16
 8002a2a:	8001      	strh	r1, [r0, #0]
 8002a2c:	0409      	lsls	r1, r1, #16
 8002a2e:	2080      	movs	r0, #128	@ 0x80
 8002a30:	0440      	lsls	r0, r0, #17
 8002a32:	4281      	cmp	r1, r0
 8002a34:	d008      	beq.n	0x8002a48
 8002a36:	2000      	movs	r0, #0
 8002a38:	e007      	b.n	0x8002a4a
 8002a3a:	0000      	movs	r0, r0
 8002a3c:	0328      	lsls	r0, r5, #12
 8002a3e:	0300      	lsls	r0, r0, #12
 8002a40:	032c      	lsls	r4, r5, #12
 8002a42:	0300      	lsls	r0, r0, #12
 8002a44:	032e      	lsls	r6, r5, #12
 8002a46:	0300      	lsls	r0, r0, #12
 8002a48:	2001      	movs	r0, #1
 8002a4a:	bc10      	pop	{r4}
 8002a4c:	bc02      	pop	{r1}
 8002a4e:	4708      	bx	r1
 8002a50:	b570      	push	{r4, r5, r6, lr}
 8002a52:	b082      	sub	sp, #8
 8002a54:	1c04      	adds	r4, r0, #0
 8002a56:	0409      	lsls	r1, r1, #16
 8002a58:	0c0b      	lsrs	r3, r1, #16
 8002a5a:	0612      	lsls	r2, r2, #24
 8002a5c:	0e16      	lsrs	r6, r2, #24
 8002a5e:	7a20      	ldrb	r0, [r4, #8]
 8002a60:	2805      	cmp	r0, #5
 8002a62:	d841      	bhi.n	0x8002ae8
 8002a64:	0080      	lsls	r0, r0, #2
 8002a66:	4902      	ldr	r1, [pc, #8]	@ (0x8002a70)
 8002a68:	1840      	adds	r0, r0, r1
 8002a6a:	6800      	ldr	r0, [r0, #0]
 8002a6c:	4687      	mov	pc, r0
 8002a6e:	0000      	movs	r0, r0
 8002a70:	2a74      	cmp	r2, #116	@ 0x74
 8002a72:	0800      	lsrs	r0, r0, #32
 8002a74:	2a8c      	cmp	r2, #140	@ 0x8c
 8002a76:	0800      	lsrs	r0, r0, #32
 8002a78:	2aac      	cmp	r2, #172	@ 0xac
 8002a7a:	0800      	lsrs	r0, r0, #32
 8002a7c:	2aac      	cmp	r2, #172	@ 0xac
 8002a7e:	0800      	lsrs	r0, r0, #32
 8002a80:	2a8c      	cmp	r2, #140	@ 0x8c
 8002a82:	0800      	lsrs	r0, r0, #32
 8002a84:	2acc      	cmp	r2, #204	@ 0xcc
 8002a86:	0800      	lsrs	r0, r0, #32
 8002a88:	2acc      	cmp	r2, #204	@ 0xcc
 8002a8a:	0800      	lsrs	r0, r0, #32
 8002a8c:	0159      	lsls	r1, r3, #5
 8002a8e:	68e0      	ldr	r0, [r4, #12]
 8002a90:	1840      	adds	r0, r0, r1
 8002a92:	01b1      	lsls	r1, r6, #6
 8002a94:	1845      	adds	r5, r0, r1
 8002a96:	7a22      	ldrb	r2, [r4, #8]
 8002a98:	7963      	ldrb	r3, [r4, #5]
 8002a9a:	79a0      	ldrb	r0, [r4, #6]
 8002a9c:	9000      	str	r0, [sp, #0]
 8002a9e:	79e0      	ldrb	r0, [r4, #7]
 8002aa0:	9001      	str	r0, [sp, #4]
 8002aa2:	1c30      	adds	r0, r6, #0
 8002aa4:	1c29      	adds	r1, r5, #0
 8002aa6:	f000 fdc3 	bl	0x8003630
 8002aaa:	e01d      	b.n	0x8002ae8
 8002aac:	18f0      	adds	r0, r6, r3
 8002aae:	0140      	lsls	r0, r0, #5
 8002ab0:	68e1      	ldr	r1, [r4, #12]
 8002ab2:	180d      	adds	r5, r1, r0
 8002ab4:	00f0      	lsls	r0, r6, #3
 8002ab6:	4904      	ldr	r1, [pc, #16]	@ (0x8002ac8)
 8002ab8:	1840      	adds	r0, r0, r1
 8002aba:	7962      	ldrb	r2, [r4, #5]
 8002abc:	79a3      	ldrb	r3, [r4, #6]
 8002abe:	1c29      	adds	r1, r5, #0
 8002ac0:	f000 feb6 	bl	0x8003830
 8002ac4:	e010      	b.n	0x8002ae8
 8002ac6:	0000      	movs	r0, r0
 8002ac8:	49ac      	ldr	r1, [pc, #688]	@ (0x8002d7c)
 8002aca:	081b      	lsrs	r3, r3, #32
 8002acc:	18f0      	adds	r0, r6, r3
 8002ace:	0140      	lsls	r0, r0, #5
 8002ad0:	68e1      	ldr	r1, [r4, #12]
 8002ad2:	180d      	adds	r5, r1, r0
 8002ad4:	0170      	lsls	r0, r6, #5
 8002ad6:	4906      	ldr	r1, [pc, #24]	@ (0x8002af0)
 8002ad8:	1840      	adds	r0, r0, r1
 8002ada:	7962      	ldrb	r2, [r4, #5]
 8002adc:	79e3      	ldrb	r3, [r4, #7]
 8002ade:	79a1      	ldrb	r1, [r4, #6]
 8002ae0:	9100      	str	r1, [sp, #0]
 8002ae2:	1c29      	adds	r1, r5, #0
 8002ae4:	f000 fedc 	bl	0x80038a0
 8002ae8:	b002      	add	sp, #8
 8002aea:	bc70      	pop	{r4, r5, r6}
 8002aec:	bc01      	pop	{r0}
 8002aee:	4700      	bx	r0
 8002af0:	51ac      	str	r4, [r5, r6]
 8002af2:	081b      	lsrs	r3, r3, #32
 8002af4:	b570      	push	{r4, r5, r6, lr}
 8002af6:	b082      	sub	sp, #8
 8002af8:	1c04      	adds	r4, r0, #0
 8002afa:	0409      	lsls	r1, r1, #16
 8002afc:	2500      	movs	r5, #0
 8002afe:	0ace      	lsrs	r6, r1, #11
 8002b00:	68e1      	ldr	r1, [r4, #12]
 8002b02:	1989      	adds	r1, r1, r6
 8002b04:	01a8      	lsls	r0, r5, #6
 8002b06:	1809      	adds	r1, r1, r0
 8002b08:	7a22      	ldrb	r2, [r4, #8]
 8002b0a:	7963      	ldrb	r3, [r4, #5]
 8002b0c:	79a0      	ldrb	r0, [r4, #6]
 8002b0e:	9000      	str	r0, [sp, #0]
 8002b10:	79e0      	ldrb	r0, [r4, #7]
 8002b12:	9001      	str	r0, [sp, #4]
 8002b14:	1c28      	adds	r0, r5, #0
 8002b16:	f000 fd8b 	bl	0x8003630
 8002b1a:	3501      	adds	r5, #1
 8002b1c:	2dff      	cmp	r5, #255	@ 0xff
 8002b1e:	ddef      	ble.n	0x8002b00
 8002b20:	0468      	lsls	r0, r5, #17
 8002b22:	0c00      	lsrs	r0, r0, #16
 8002b24:	b002      	add	sp, #8
 8002b26:	bc70      	pop	{r4, r5, r6}
 8002b28:	bc02      	pop	{r1}
 8002b2a:	4708      	bx	r1
 8002b2c:	b570      	push	{r4, r5, r6, lr}
 8002b2e:	1c06      	adds	r6, r0, #0
 8002b30:	0409      	lsls	r1, r1, #16
 8002b32:	2500      	movs	r5, #0
 8002b34:	0acc      	lsrs	r4, r1, #11
 8002b36:	68f1      	ldr	r1, [r6, #12]
 8002b38:	1909      	adds	r1, r1, r4
 8002b3a:	00e8      	lsls	r0, r5, #3
 8002b3c:	4a07      	ldr	r2, [pc, #28]	@ (0x8002b5c)
 8002b3e:	1880      	adds	r0, r0, r2
 8002b40:	7972      	ldrb	r2, [r6, #5]
 8002b42:	79b3      	ldrb	r3, [r6, #6]
 8002b44:	f000 fe74 	bl	0x8003830
 8002b48:	3420      	adds	r4, #32
 8002b4a:	3501      	adds	r5, #1
 8002b4c:	2dff      	cmp	r5, #255	@ 0xff
 8002b4e:	ddf2      	ble.n	0x8002b36
 8002b50:	0428      	lsls	r0, r5, #16
 8002b52:	0c00      	lsrs	r0, r0, #16
 8002b54:	bc70      	pop	{r4, r5, r6}
 8002b56:	bc02      	pop	{r1}
 8002b58:	4708      	bx	r1
 8002b5a:	0000      	movs	r0, r0
 8002b5c:	49ac      	ldr	r1, [pc, #688]	@ (0x8002e10)
 8002b5e:	081b      	lsrs	r3, r3, #32
 8002b60:	b5f0      	push	{r4, r5, r6, r7, lr}
 8002b62:	b081      	sub	sp, #4
 8002b64:	1c05      	adds	r5, r0, #0
 8002b66:	0409      	lsls	r1, r1, #16
 8002b68:	2700      	movs	r7, #0
 8002b6a:	0ace      	lsrs	r6, r1, #11
 8002b6c:	68e9      	ldr	r1, [r5, #12]
 8002b6e:	1989      	adds	r1, r1, r6
 8002b70:	0178      	lsls	r0, r7, #5
 8002b72:	4a09      	ldr	r2, [pc, #36]	@ (0x8002b98)
 8002b74:	1880      	adds	r0, r0, r2
 8002b76:	796a      	ldrb	r2, [r5, #5]
 8002b78:	79eb      	ldrb	r3, [r5, #7]
 8002b7a:	79ac      	ldrb	r4, [r5, #6]
 8002b7c:	9400      	str	r4, [sp, #0]
 8002b7e:	f000 fe8f 	bl	0x80038a0
 8002b82:	3620      	adds	r6, #32
 8002b84:	3701      	adds	r7, #1
 8002b86:	2fff      	cmp	r7, #255	@ 0xff
 8002b88:	ddf0      	ble.n	0x8002b6c
 8002b8a:	0438      	lsls	r0, r7, #16
 8002b8c:	0c00      	lsrs	r0, r0, #16
 8002b8e:	b001      	add	sp, #4
 8002b90:	bcf0      	pop	{r4, r5, r6, r7}
 8002b92:	bc02      	pop	{r1}
 8002b94:	4708      	bx	r1
 8002b96:	0000      	movs	r0, r0
 8002b98:	51ac      	str	r4, [r5, r6]
 8002b9a:	081b      	lsrs	r3, r3, #32
 8002b9c:	b570      	push	{r4, r5, r6, lr}
 8002b9e:	1c06      	adds	r6, r0, #0
 8002ba0:	0409      	lsls	r1, r1, #16
 8002ba2:	2500      	movs	r5, #0
 8002ba4:	0acc      	lsrs	r4, r1, #11
 8002ba6:	68f1      	ldr	r1, [r6, #12]
 8002ba8:	1909      	adds	r1, r1, r4
 8002baa:	00e8      	lsls	r0, r5, #3
 8002bac:	4a07      	ldr	r2, [pc, #28]	@ (0x8002bcc)
 8002bae:	1880      	adds	r0, r0, r2
 8002bb0:	7972      	ldrb	r2, [r6, #5]
 8002bb2:	79b3      	ldrb	r3, [r6, #6]
 8002bb4:	f000 fe3c 	bl	0x8003830
 8002bb8:	3420      	adds	r4, #32
 8002bba:	3501      	adds	r5, #1
 8002bbc:	2dff      	cmp	r5, #255	@ 0xff
 8002bbe:	ddf2      	ble.n	0x8002ba6
 8002bc0:	0428      	lsls	r0, r5, #16
 8002bc2:	0c00      	lsrs	r0, r0, #16
 8002bc4:	bc70      	pop	{r4, r5, r6}
 8002bc6:	bc02      	pop	{r1}
 8002bc8:	4708      	bx	r1
 8002bca:	0000      	movs	r0, r0
 8002bcc:	acac      	add	r4, sp, #688	@ 0x2b0
 8002bce:	081b      	lsrs	r3, r3, #32
 8002bd0:	b510      	push	{r4, lr}
 8002bd2:	b081      	sub	sp, #4
 8002bd4:	1c04      	adds	r4, r0, #0
 8002bd6:	2000      	movs	r0, #0
 8002bd8:	82e1      	strh	r1, [r4, #22]
 8002bda:	9000      	str	r0, [sp, #0]
 8002bdc:	6821      	ldr	r1, [r4, #0]
 8002bde:	8ae0      	ldrh	r0, [r4, #22]
 8002be0:	0140      	lsls	r0, r0, #5
 8002be2:	68c9      	ldr	r1, [r1, #12]
 8002be4:	1809      	adds	r1, r1, r0
 8002be6:	4a0c      	ldr	r2, [pc, #48]	@ (0x8002c18)
 8002be8:	4668      	mov	r0, sp
 8002bea:	f1ae fb51 	bl	0x81b1290
 8002bee:	480b      	ldr	r0, [pc, #44]	@ (0x8002c1c)
 8002bf0:	6823      	ldr	r3, [r4, #0]
 8002bf2:	8ae2      	ldrh	r2, [r4, #22]
 8002bf4:	3201      	adds	r2, #1
 8002bf6:	0152      	lsls	r2, r2, #5
 8002bf8:	68d9      	ldr	r1, [r3, #12]
 8002bfa:	1889      	adds	r1, r1, r2
 8002bfc:	795a      	ldrb	r2, [r3, #5]
 8002bfe:	799b      	ldrb	r3, [r3, #6]
 8002c00:	f000 fe16 	bl	0x8003830
 8002c04:	4906      	ldr	r1, [pc, #24]	@ (0x8002c20)
 8002c06:	1c08      	adds	r0, r1, #0
 8002c08:	8ae4      	ldrh	r4, [r4, #22]
 8002c0a:	1900      	adds	r0, r0, r4
 8002c0c:	0400      	lsls	r0, r0, #16
 8002c0e:	0c00      	lsrs	r0, r0, #16
 8002c10:	b001      	add	sp, #4
 8002c12:	bc10      	pop	{r4}
 8002c14:	bc02      	pop	{r1}
 8002c16:	4708      	bx	r1
 8002c18:	0008      	movs	r0, r1
 8002c1a:	0100      	lsls	r0, r0, #4
 8002c1c:	3a84      	subs	r2, #132	@ 0x84
 8002c1e:	081b      	lsrs	r3, r3, #32
 8002c20:	025a      	lsls	r2, r3, #9
 8002c22:	0000      	movs	r0, r0
 8002c24:	4770      	bx	lr
 8002c26:	0000      	movs	r0, r0
 8002c28:	b570      	push	{r4, r5, r6, lr}
 8002c2a:	1c04      	adds	r4, r0, #0
 8002c2c:	1c08      	adds	r0, r1, #0
 8002c2e:	1c22      	adds	r2, r4, #0
 8002c30:	490c      	ldr	r1, [pc, #48]	@ (0x8002c64)
 8002c32:	c968      	ldmia	r1!, {r3, r5, r6}
 8002c34:	c268      	stmia	r2!, {r3, r5, r6}
 8002c36:	c968      	ldmia	r1!, {r3, r5, r6}
 8002c38:	c268      	stmia	r2!, {r3, r5, r6}
 8002c3a:	c968      	ldmia	r1!, {r3, r5, r6}
 8002c3c:	c268      	stmia	r2!, {r3, r5, r6}
 8002c3e:	f001 faf3 	bl	0x8004228
 8002c42:	6020      	str	r0, [r4, #0]
 8002c44:	7a41      	ldrb	r1, [r0, #9]
 8002c46:	72a1      	strb	r1, [r4, #10]
 8002c48:	7a01      	ldrb	r1, [r0, #8]
 8002c4a:	72e1      	strb	r1, [r4, #11]
 8002c4c:	7941      	ldrb	r1, [r0, #5]
 8002c4e:	7321      	strb	r1, [r4, #12]
 8002c50:	7981      	ldrb	r1, [r0, #6]
 8002c52:	7361      	strb	r1, [r4, #13]
 8002c54:	79c1      	ldrb	r1, [r0, #7]
 8002c56:	73a1      	strb	r1, [r4, #14]
 8002c58:	7900      	ldrb	r0, [r0, #4]
 8002c5a:	73e0      	strb	r0, [r4, #15]
 8002c5c:	bc70      	pop	{r4, r5, r6}
 8002c5e:	bc01      	pop	{r0}
 8002c60:	4700      	bx	r0
 8002c62:	0000      	movs	r0, r0
 8002c64:	3484      	adds	r4, #132	@ 0x84
 8002c66:	081b      	lsrs	r3, r3, #32
 8002c68:	b570      	push	{r4, r5, r6, lr}
 8002c6a:	464e      	mov	r6, r9
 8002c6c:	4645      	mov	r5, r8
 8002c6e:	b460      	push	{r5, r6}
 8002c70:	9c06      	ldr	r4, [sp, #24]
 8002c72:	46a1      	mov	r9, r4
 8002c74:	2400      	movs	r4, #0
 8002c76:	46a0      	mov	r8, r4
 8002c78:	2600      	movs	r6, #0
 8002c7a:	2401      	movs	r4, #1
 8002c7c:	8084      	strh	r4, [r0, #4]
 8002c7e:	80c6      	strh	r6, [r0, #6]
 8002c80:	4644      	mov	r4, r8
 8002c82:	7204      	strb	r4, [r0, #8]
 8002c84:	6805      	ldr	r5, [r0, #0]
 8002c86:	7a6c      	ldrb	r4, [r5, #9]
 8002c88:	7284      	strb	r4, [r0, #10]
 8002c8a:	7a2c      	ldrb	r4, [r5, #8]
 8002c8c:	72c4      	strb	r4, [r0, #11]
 8002c8e:	796c      	ldrb	r4, [r5, #5]
 8002c90:	7304      	strb	r4, [r0, #12]
 8002c92:	79ac      	ldrb	r4, [r5, #6]
 8002c94:	7344      	strb	r4, [r0, #13]
 8002c96:	79ec      	ldrb	r4, [r5, #7]
 8002c98:	7384      	strb	r4, [r0, #14]
 8002c9a:	792c      	ldrb	r4, [r5, #4]
 8002c9c:	73c4      	strb	r4, [r0, #15]
 8002c9e:	6101      	str	r1, [r0, #16]
 8002ca0:	8286      	strh	r6, [r0, #20]
 8002ca2:	82c2      	strh	r2, [r0, #22]
 8002ca4:	8306      	strh	r6, [r0, #24]
 8002ca6:	7683      	strb	r3, [r0, #26]
 8002ca8:	4641      	mov	r1, r8
 8002caa:	76c1      	strb	r1, [r0, #27]
 8002cac:	464c      	mov	r4, r9
 8002cae:	7704      	strb	r4, [r0, #28]
 8002cb0:	7741      	strb	r1, [r0, #29]
 8002cb2:	7241      	strb	r1, [r0, #9]
 8002cb4:	bc18      	pop	{r3, r4}
 8002cb6:	4698      	mov	r8, r3
 8002cb8:	46a1      	mov	r9, r4
 8002cba:	bc70      	pop	{r4, r5, r6}
 8002cbc:	bc01      	pop	{r0}
 8002cbe:	4700      	bx	r0
 8002cc0:	b570      	push	{r4, r5, r6, lr}
 8002cc2:	b081      	sub	sp, #4
 8002cc4:	1c06      	adds	r6, r0, #0
 8002cc6:	1c0d      	adds	r5, r1, #0
 8002cc8:	2005      	movs	r0, #5
 8002cca:	f001 faad 	bl	0x8004228
 8002cce:	4c0a      	ldr	r4, [pc, #40]	@ (0x8002cf8)
 8002cd0:	6020      	str	r0, [r4, #0]
 8002cd2:	2000      	movs	r0, #0
 8002cd4:	9000      	str	r0, [sp, #0]
 8002cd6:	1c20      	adds	r0, r4, #0
 8002cd8:	1c29      	adds	r1, r5, #0
 8002cda:	2200      	movs	r2, #0
 8002cdc:	2300      	movs	r3, #0
 8002cde:	f7ff ffc3 	bl	0x8002c68
 8002ce2:	2002      	movs	r0, #2
 8002ce4:	72a0      	strb	r0, [r4, #10]
 8002ce6:	6226      	str	r6, [r4, #32]
 8002ce8:	1c20      	adds	r0, r4, #0
 8002cea:	f000 f87d 	bl	0x8002de8
 8002cee:	b001      	add	sp, #4
 8002cf0:	bc70      	pop	{r4, r5, r6}
 8002cf2:	bc01      	pop	{r0}
 8002cf4:	4700      	bx	r0
 8002cf6:	0000      	movs	r0, r0
 8002cf8:	31cc      	adds	r1, #204	@ 0xcc
 8002cfa:	0202      	lsls	r2, r0, #8
 8002cfc:	b510      	push	{r4, lr}
 8002cfe:	b081      	sub	sp, #4
 8002d00:	9c03      	ldr	r4, [sp, #12]
 8002d02:	0412      	lsls	r2, r2, #16
 8002d04:	0c12      	lsrs	r2, r2, #16
 8002d06:	061b      	lsls	r3, r3, #24
 8002d08:	0e1b      	lsrs	r3, r3, #24
 8002d0a:	0624      	lsls	r4, r4, #24
 8002d0c:	0e24      	lsrs	r4, r4, #24
 8002d0e:	9400      	str	r4, [sp, #0]
 8002d10:	f7ff ffaa 	bl	0x8002c68
 8002d14:	b001      	add	sp, #4
 8002d16:	bc10      	pop	{r4}
 8002d18:	bc01      	pop	{r0}
 8002d1a:	4700      	bx	r0
 8002d1c:	b5f0      	push	{r4, r5, r6, r7, lr}
 8002d1e:	4647      	mov	r7, r8
 8002d20:	b480      	push	{r7}
 8002d22:	b081      	sub	sp, #4
 8002d24:	1c07      	adds	r7, r0, #0
 8002d26:	9d07      	ldr	r5, [sp, #28]
 8002d28:	0412      	lsls	r2, r2, #16
 8002d2a:	0c12      	lsrs	r2, r2, #16
 8002d2c:	061b      	lsls	r3, r3, #24
 8002d2e:	0e1b      	lsrs	r3, r3, #24
 8002d30:	062d      	lsls	r5, r5, #24
 8002d32:	0e2d      	lsrs	r5, r5, #24
 8002d34:	4e1a      	ldr	r6, [pc, #104]	@ (0x8002da0)
 8002d36:	2000      	movs	r0, #0
 8002d38:	4680      	mov	r8, r0
 8002d3a:	2400      	movs	r4, #0
 8002d3c:	2003      	movs	r0, #3
 8002d3e:	86f0      	strh	r0, [r6, #54]	@ 0x36
 8002d40:	86b4      	strh	r4, [r6, #52]	@ 0x34
 8002d42:	4818      	ldr	r0, [pc, #96]	@ (0x8002da4)
 8002d44:	4644      	mov	r4, r8
 8002d46:	7004      	strb	r4, [r0, #0]
 8002d48:	4c17      	ldr	r4, [pc, #92]	@ (0x8002da8)
 8002d4a:	2016      	movs	r0, #22
 8002d4c:	7020      	strb	r0, [r4, #0]
 8002d4e:	9500      	str	r5, [sp, #0]
 8002d50:	1c38      	adds	r0, r7, #0
 8002d52:	f7ff ff89 	bl	0x8002c68
 8002d56:	7ab8      	ldrb	r0, [r7, #10]
 8002d58:	2800      	cmp	r0, #0
 8002d5a:	d11a      	bne.n	0x8002d92
 8002d5c:	4813      	ldr	r0, [pc, #76]	@ (0x8002dac)
 8002d5e:	683b      	ldr	r3, [r7, #0]
 8002d60:	8afa      	ldrh	r2, [r7, #22]
 8002d62:	8b39      	ldrh	r1, [r7, #24]
 8002d64:	1852      	adds	r2, r2, r1
 8002d66:	0152      	lsls	r2, r2, #5
 8002d68:	68d9      	ldr	r1, [r3, #12]
 8002d6a:	1889      	adds	r1, r1, r2
 8002d6c:	7b7b      	ldrb	r3, [r7, #13]
 8002d6e:	1c1a      	adds	r2, r3, #0
 8002d70:	f000 fd5e 	bl	0x8003830
 8002d74:	480e      	ldr	r0, [pc, #56]	@ (0x8002db0)
 8002d76:	683b      	ldr	r3, [r7, #0]
 8002d78:	8afa      	ldrh	r2, [r7, #22]
 8002d7a:	8b39      	ldrh	r1, [r7, #24]
 8002d7c:	1852      	adds	r2, r2, r1
 8002d7e:	0152      	lsls	r2, r2, #5
 8002d80:	68d9      	ldr	r1, [r3, #12]
 8002d82:	1889      	adds	r1, r1, r2
 8002d84:	3120      	adds	r1, #32
 8002d86:	7b3a      	ldrb	r2, [r7, #12]
 8002d88:	7b7b      	ldrb	r3, [r7, #13]
 8002d8a:	f000 fd51 	bl	0x8003830
 8002d8e:	2004      	movs	r0, #4
 8002d90:	8338      	strh	r0, [r7, #24]
 8002d92:	b001      	add	sp, #4
 8002d94:	bc08      	pop	{r3}
 8002d96:	4698      	mov	r8, r3
 8002d98:	bcf0      	pop	{r4, r5, r6, r7}
 8002d9a:	bc01      	pop	{r0}
 8002d9c:	4700      	bx	r0
 8002d9e:	0000      	movs	r0, r0
 8002da0:	16e0      	asrs	r0, r4, #27
 8002da2:	0300      	lsls	r0, r0, #12
 8002da4:	0324      	lsls	r4, r4, #12
 8002da6:	0300      	lsls	r0, r0, #12
 8002da8:	0325      	lsls	r5, r4, #12
 8002daa:	0300      	lsls	r0, r0, #12
 8002dac:	3a84      	subs	r2, #132	@ 0x84
 8002dae:	081b      	lsrs	r3, r3, #32
 8002db0:	4d1c      	ldr	r5, [pc, #112]	@ (0x8002e24)
 8002db2:	081b      	lsrs	r3, r3, #32
 8002db4:	b570      	push	{r4, r5, r6, lr}
 8002db6:	4646      	mov	r6, r8
 8002db8:	b440      	push	{r6}
 8002dba:	1c04      	adds	r4, r0, #0
 8002dbc:	6926      	ldr	r6, [r4, #16]
 8002dbe:	8aa0      	ldrh	r0, [r4, #20]
 8002dc0:	4680      	mov	r8, r0
 8002dc2:	6121      	str	r1, [r4, #16]
 8002dc4:	2000      	movs	r0, #0
 8002dc6:	82a0      	strh	r0, [r4, #20]
 8002dc8:	2502      	movs	r5, #2
 8002dca:	80a5      	strh	r5, [r4, #4]
 8002dcc:	1c20      	adds	r0, r4, #0
 8002dce:	f000 f80b 	bl	0x8002de8
 8002dd2:	0600      	lsls	r0, r0, #24
 8002dd4:	0e00      	lsrs	r0, r0, #24
 8002dd6:	6126      	str	r6, [r4, #16]
 8002dd8:	4641      	mov	r1, r8
 8002dda:	82a1      	strh	r1, [r4, #20]
 8002ddc:	80a5      	strh	r5, [r4, #4]
 8002dde:	bc08      	pop	{r3}
 8002de0:	4698      	mov	r8, r3
 8002de2:	bc70      	pop	{r4, r5, r6}
 8002de4:	bc02      	pop	{r1}
 8002de6:	4708      	bx	r1
 8002de8:	b510      	push	{r4, lr}
 8002dea:	1c04      	adds	r4, r0, #0
 8002dec:	e01c      	b.n	0x8002e28
 8002dee:	2806      	cmp	r0, #6
 8002df0:	d107      	bne.n	0x8002e02
 8002df2:	2000      	movs	r0, #0
 8002df4:	76e0      	strb	r0, [r4, #27]
 8002df6:	7f60      	ldrb	r0, [r4, #29]
 8002df8:	3002      	adds	r0, #2
 8002dfa:	7760      	strb	r0, [r4, #29]
 8002dfc:	2002      	movs	r0, #2
 8002dfe:	80a0      	strh	r0, [r4, #4]
 8002e00:	e00f      	b.n	0x8002e22
 8002e02:	2807      	cmp	r0, #7
 8002e04:	d10d      	bne.n	0x8002e22
 8002e06:	8aa1      	ldrh	r1, [r4, #20]
 8002e08:	1c48      	adds	r0, r1, #1
 8002e0a:	82a0      	strh	r0, [r4, #20]
 8002e0c:	0409      	lsls	r1, r1, #16
 8002e0e:	0c09      	lsrs	r1, r1, #16
 8002e10:	6920      	ldr	r0, [r4, #16]
 8002e12:	1840      	adds	r0, r0, r1
 8002e14:	7800      	ldrb	r0, [r0, #0]
 8002e16:	f001 fc5d 	bl	0x80046d4
 8002e1a:	1c01      	adds	r1, r0, #0
 8002e1c:	1c20      	adds	r0, r4, #0
 8002e1e:	f7ff ffc9 	bl	0x8002db4
 8002e22:	1c20      	adds	r0, r4, #0
 8002e24:	f000 fa68 	bl	0x80032f8
 8002e28:	88a0      	ldrh	r0, [r4, #4]
 8002e2a:	2800      	cmp	r0, #0
 8002e2c:	d1df      	bne.n	0x8002dee
 8002e2e:	2001      	movs	r0, #1
 8002e30:	bc10      	pop	{r4}
 8002e32:	bc02      	pop	{r1}
 8002e34:	4708      	bx	r1
 8002e36:	0000      	movs	r0, r0
 8002e38:	b510      	push	{r4, lr}
 8002e3a:	2400      	movs	r4, #0
 8002e3c:	2300      	movs	r3, #0
 8002e3e:	2202      	movs	r2, #2
 8002e40:	8082      	strh	r2, [r0, #4]
 8002e42:	6101      	str	r1, [r0, #16]
 8002e44:	8283      	strh	r3, [r0, #20]
 8002e46:	80c3      	strh	r3, [r0, #6]
 8002e48:	7204      	strb	r4, [r0, #8]
 8002e4a:	7244      	strb	r4, [r0, #9]
 8002e4c:	bc10      	pop	{r4}
 8002e4e:	bc01      	pop	{r0}
 8002e50:	4700      	bx	r0
 8002e52:	0000      	movs	r0, r0
 8002e54:	b510      	push	{r4, lr}
 8002e56:	1c04      	adds	r4, r0, #0
 8002e58:	e011      	b.n	0x8002e7e
 8002e5a:	2806      	cmp	r0, #6
 8002e5c:	d106      	bne.n	0x8002e6c
 8002e5e:	2000      	movs	r0, #0
 8002e60:	76e0      	strb	r0, [r4, #27]
 8002e62:	7f60      	ldrb	r0, [r4, #29]
 8002e64:	3002      	adds	r0, #2
 8002e66:	7760      	strb	r0, [r4, #29]
 8002e68:	2002      	movs	r0, #2
 8002e6a:	80a0      	strh	r0, [r4, #4]
 8002e6c:	1c20      	adds	r0, r4, #0
 8002e6e:	f000 fa43 	bl	0x80032f8
 8002e72:	0600      	lsls	r0, r0, #24
 8002e74:	0e00      	lsrs	r0, r0, #24
 8002e76:	2801      	cmp	r0, #1
 8002e78:	d101      	bne.n	0x8002e7e
 8002e7a:	2000      	movs	r0, #0
 8002e7c:	e003      	b.n	0x8002e86
 8002e7e:	88a0      	ldrh	r0, [r4, #4]
 8002e80:	2800      	cmp	r0, #0
 8002e82:	d1ea      	bne.n	0x8002e5a
 8002e84:	2001      	movs	r0, #1
 8002e86:	bc10      	pop	{r4}
 8002e88:	bc02      	pop	{r1}
 8002e8a:	4708      	bx	r1
 8002e8c:	b510      	push	{r4, lr}
 8002e8e:	1c04      	adds	r4, r0, #0
 8002e90:	88a0      	ldrh	r0, [r4, #4]
 8002e92:	280a      	cmp	r0, #10
 8002e94:	d900      	bls.n	0x8002e98
 8002e96:	e085      	b.n	0x8002fa4
 8002e98:	0080      	lsls	r0, r0, #2
 8002e9a:	4902      	ldr	r1, [pc, #8]	@ (0x8002ea4)
 8002e9c:	1840      	adds	r0, r0, r1
 8002e9e:	6800      	ldr	r0, [r0, #0]
 8002ea0:	4687      	mov	pc, r0
 8002ea2:	0000      	movs	r0, r0
 8002ea4:	2ea8      	cmp	r6, #168	@ 0xa8
 8002ea6:	0800      	lsrs	r0, r0, #32
 8002ea8:	2fa8      	cmp	r7, #168	@ 0xa8
 8002eaa:	0800      	lsrs	r0, r0, #32
 8002eac:	2f8c      	cmp	r7, #140	@ 0x8c
 8002eae:	0800      	lsrs	r0, r0, #32
 8002eb0:	2fac      	cmp	r7, #172	@ 0xac
 8002eb2:	0800      	lsrs	r0, r0, #32
 8002eb4:	2f10      	cmp	r7, #16
 8002eb6:	0800      	lsrs	r0, r0, #32
 8002eb8:	2f3c      	cmp	r7, #60	@ 0x3c
 8002eba:	0800      	lsrs	r0, r0, #32
 8002ebc:	2ed4      	cmp	r6, #212	@ 0xd4
 8002ebe:	0800      	lsrs	r0, r0, #32
 8002ec0:	2f80      	cmp	r7, #128	@ 0x80
 8002ec2:	0800      	lsrs	r0, r0, #32
 8002ec4:	2f78      	cmp	r7, #120	@ 0x78
 8002ec6:	0800      	lsrs	r0, r0, #32
 8002ec8:	2f48      	cmp	r7, #72	@ 0x48
 8002eca:	0800      	lsrs	r0, r0, #32
 8002ecc:	2f60      	cmp	r7, #96	@ 0x60
 8002ece:	0800      	lsrs	r0, r0, #32
 8002ed0:	2f94      	cmp	r7, #148	@ 0x94
 8002ed2:	0800      	lsrs	r0, r0, #32
 8002ed4:	1c20      	adds	r0, r4, #0
 8002ed6:	f000 fd45 	bl	0x8003964
 8002eda:	0600      	lsls	r0, r0, #24
 8002edc:	0e00      	lsrs	r0, r0, #24
 8002ede:	2801      	cmp	r0, #1
 8002ee0:	d107      	bne.n	0x8002ef2
 8002ee2:	7a60      	ldrb	r0, [r4, #9]
 8002ee4:	3801      	subs	r0, #1
 8002ee6:	7260      	strb	r0, [r4, #9]
 8002ee8:	0600      	lsls	r0, r0, #24
 8002eea:	2800      	cmp	r0, #0
 8002eec:	d000      	beq.n	0x8002ef0
 8002eee:	e090      	b.n	0x8003012
 8002ef0:	e009      	b.n	0x8002f06
 8002ef2:	4806      	ldr	r0, [pc, #24]	@ (0x8002f0c)
 8002ef4:	8dc1      	ldrh	r1, [r0, #46]	@ 0x2e
 8002ef6:	2003      	movs	r0, #3
 8002ef8:	4008      	ands	r0, r1
 8002efa:	2800      	cmp	r0, #0
 8002efc:	d100      	bne.n	0x8002f00
 8002efe:	e088      	b.n	0x8003012
 8002f00:	2005      	movs	r0, #5
 8002f02:	f06f fae3 	bl	0x80724cc
 8002f06:	2002      	movs	r0, #2
 8002f08:	80a0      	strh	r0, [r4, #4]
 8002f0a:	e082      	b.n	0x8003012
 8002f0c:	16e0      	asrs	r0, r4, #27
 8002f0e:	0300      	lsls	r0, r0, #12
 8002f10:	1c20      	adds	r0, r4, #0
 8002f12:	f000 fd27 	bl	0x8003964
 8002f16:	0600      	lsls	r0, r0, #24
 8002f18:	0e00      	lsrs	r0, r0, #24
 8002f1a:	2801      	cmp	r0, #1
 8002f1c:	d00e      	beq.n	0x8002f3c
 8002f1e:	4a06      	ldr	r2, [pc, #24]	@ (0x8002f38)
 8002f20:	8d91      	ldrh	r1, [r2, #44]	@ 0x2c
 8002f22:	2003      	movs	r0, #3
 8002f24:	4008      	ands	r0, r1
 8002f26:	2800      	cmp	r0, #0
 8002f28:	d008      	beq.n	0x8002f3c
 8002f2a:	8e90      	ldrh	r0, [r2, #52]	@ 0x34
 8002f2c:	2801      	cmp	r0, #1
 8002f2e:	d105      	bne.n	0x8002f3c
 8002f30:	2000      	movs	r0, #0
 8002f32:	7260      	strb	r0, [r4, #9]
 8002f34:	e033      	b.n	0x8002f9e
 8002f36:	0000      	movs	r0, r0
 8002f38:	16e0      	asrs	r0, r4, #27
 8002f3a:	0300      	lsls	r0, r0, #12
 8002f3c:	7a60      	ldrb	r0, [r4, #9]
 8002f3e:	2800      	cmp	r0, #0
 8002f40:	d02d      	beq.n	0x8002f9e
 8002f42:	3801      	subs	r0, #1
 8002f44:	7260      	strb	r0, [r4, #9]
 8002f46:	e027      	b.n	0x8002f98
 8002f48:	1c20      	adds	r0, r4, #0
 8002f4a:	f001 f82b 	bl	0x8003fa4
 8002f4e:	0600      	lsls	r0, r0, #24
 8002f50:	2800      	cmp	r0, #0
 8002f52:	d05e      	beq.n	0x8003012
 8002f54:	1c20      	adds	r0, r4, #0
 8002f56:	f000 fe27 	bl	0x8003ba8
 8002f5a:	2002      	movs	r0, #2
 8002f5c:	80a0      	strh	r0, [r4, #4]
 8002f5e:	e058      	b.n	0x8003012
 8002f60:	1c20      	adds	r0, r4, #0
 8002f62:	f001 f81f 	bl	0x8003fa4
 8002f66:	0600      	lsls	r0, r0, #24
 8002f68:	2800      	cmp	r0, #0
 8002f6a:	d052      	beq.n	0x8003012
 8002f6c:	1c20      	adds	r0, r4, #0
 8002f6e:	f000 fd1b 	bl	0x80039a8
 8002f72:	2002      	movs	r0, #2
 8002f74:	80a0      	strh	r0, [r4, #4]
 8002f76:	e04c      	b.n	0x8003012
 8002f78:	8aa0      	ldrh	r0, [r4, #20]
 8002f7a:	3001      	adds	r0, #1
 8002f7c:	82a0      	strh	r0, [r4, #20]
 8002f7e:	e00e      	b.n	0x8002f9e
 8002f80:	1c20      	adds	r0, r4, #0
 8002f82:	f000 fd11 	bl	0x80039a8
 8002f86:	2002      	movs	r0, #2
 8002f88:	80a0      	strh	r0, [r4, #4]
 8002f8a:	e042      	b.n	0x8003012
 8002f8c:	1c20      	adds	r0, r4, #0
 8002f8e:	f000 fe0b 	bl	0x8003ba8
 8002f92:	e00b      	b.n	0x8002fac
 8002f94:	f06f fb18 	bl	0x80725c8
 8002f98:	0600      	lsls	r0, r0, #24
 8002f9a:	2800      	cmp	r0, #0
 8002f9c:	d139      	bne.n	0x8003012
 8002f9e:	2002      	movs	r0, #2
 8002fa0:	80a0      	strh	r0, [r4, #4]
 8002fa2:	e003      	b.n	0x8002fac
 8002fa4:	2000      	movs	r0, #0
 8002fa6:	80a0      	strh	r0, [r4, #4]
 8002fa8:	2001      	movs	r0, #1
 8002faa:	e033      	b.n	0x8003014
 8002fac:	1c20      	adds	r0, r4, #0
 8002fae:	f000 f9a3 	bl	0x80032f8
 8002fb2:	88a0      	ldrh	r0, [r4, #4]
 8002fb4:	280a      	cmp	r0, #10
 8002fb6:	d826      	bhi.n	0x8003006
 8002fb8:	0080      	lsls	r0, r0, #2
 8002fba:	4902      	ldr	r1, [pc, #8]	@ (0x8002fc4)
 8002fbc:	1840      	adds	r0, r0, r1
 8002fbe:	6800      	ldr	r0, [r0, #0]
 8002fc0:	4687      	mov	pc, r0
 8002fc2:	0000      	movs	r0, r0
 8002fc4:	2fc8      	cmp	r7, #200	@ 0xc8
 8002fc6:	0800      	lsrs	r0, r0, #32
 8002fc8:	2fa8      	cmp	r7, #168	@ 0xa8
 8002fca:	0800      	lsrs	r0, r0, #32
 8002fcc:	3006      	adds	r0, #6
 8002fce:	0800      	lsrs	r0, r0, #32
 8002fd0:	3006      	adds	r0, #6
 8002fd2:	0800      	lsrs	r0, r0, #32
 8002fd4:	3006      	adds	r0, #6
 8002fd6:	0800      	lsrs	r0, r0, #32
 8002fd8:	3012      	adds	r0, #18
 8002fda:	0800      	lsrs	r0, r0, #32
 8002fdc:	2ff4      	cmp	r7, #244	@ 0xf4
 8002fde:	0800      	lsrs	r0, r0, #32
 8002fe0:	3012      	adds	r0, #18
 8002fe2:	0800      	lsrs	r0, r0, #32
 8002fe4:	3006      	adds	r0, #6
 8002fe6:	0800      	lsrs	r0, r0, #32
 8002fe8:	2ff4      	cmp	r7, #244	@ 0xf4
 8002fea:	0800      	lsrs	r0, r0, #32
 8002fec:	2ff4      	cmp	r7, #244	@ 0xf4
 8002fee:	0800      	lsrs	r0, r0, #32
 8002ff0:	3012      	adds	r0, #18
 8002ff2:	0800      	lsrs	r0, r0, #32
 8002ff4:	1c20      	adds	r0, r4, #0
 8002ff6:	f000 fcb5 	bl	0x8003964
 8002ffa:	0600      	lsls	r0, r0, #24
 8002ffc:	0e00      	lsrs	r0, r0, #24
 8002ffe:	2801      	cmp	r0, #1
 8003000:	d107      	bne.n	0x8003012
 8003002:	203c      	movs	r0, #60	@ 0x3c
 8003004:	e004      	b.n	0x8003010
 8003006:	2003      	movs	r0, #3
 8003008:	80a0      	strh	r0, [r4, #4]
 800300a:	1c20      	adds	r0, r4, #0
 800300c:	f000 fc94 	bl	0x8003938
 8003010:	7260      	strb	r0, [r4, #9]
 8003012:	2000      	movs	r0, #0
 8003014:	bc10      	pop	{r4}
 8003016:	bc02      	pop	{r1}
 8003018:	4708      	bx	r1
 800301a:	0000      	movs	r0, r0
 800301c:	b500      	push	{lr}
 800301e:	4a04      	ldr	r2, [pc, #16]	@ (0x8003030)
 8003020:	2100      	movs	r1, #0
 8003022:	7011      	strb	r1, [r2, #0]
 8003024:	f7ff ff32 	bl	0x8002e8c
 8003028:	0600      	lsls	r0, r0, #24
 800302a:	0e00      	lsrs	r0, r0, #24
 800302c:	bc02      	pop	{r1}
 800302e:	4708      	bx	r1
 8003030:	0324      	lsls	r4, r4, #12
 8003032:	0300      	lsls	r0, r0, #12
 8003034:	b530      	push	{r4, r5, lr}
 8003036:	4d08      	ldr	r5, [pc, #32]	@ (0x8003058)
 8003038:	2101      	movs	r1, #1
 800303a:	7029      	strb	r1, [r5, #0]
 800303c:	4c07      	ldr	r4, [pc, #28]	@ (0x800305c)
 800303e:	211a      	movs	r1, #26
 8003040:	7021      	strb	r1, [r4, #0]
 8003042:	f7ff ff23 	bl	0x8002e8c
 8003046:	0600      	lsls	r0, r0, #24
 8003048:	0e00      	lsrs	r0, r0, #24
 800304a:	2116      	movs	r1, #22
 800304c:	7021      	strb	r1, [r4, #0]
 800304e:	2100      	movs	r1, #0
 8003050:	7029      	strb	r1, [r5, #0]
 8003052:	bc30      	pop	{r4, r5}
 8003054:	bc02      	pop	{r1}
 8003056:	4708      	bx	r1
 8003058:	0324      	lsls	r4, r4, #12
 800305a:	0300      	lsls	r0, r0, #12
 800305c:	0325      	lsls	r5, r4, #12
 800305e:	0300      	lsls	r0, r0, #12
 8003060:	b510      	push	{r4, lr}
 8003062:	4c06      	ldr	r4, [pc, #24]	@ (0x800307c)
 8003064:	2102      	movs	r1, #2
 8003066:	7021      	strb	r1, [r4, #0]
 8003068:	f7ff ff10 	bl	0x8002e8c
 800306c:	0600      	lsls	r0, r0, #24
 800306e:	0e00      	lsrs	r0, r0, #24
 8003070:	2100      	movs	r1, #0
 8003072:	7021      	strb	r1, [r4, #0]
 8003074:	bc10      	pop	{r4}
 8003076:	bc02      	pop	{r1}
 8003078:	4708      	bx	r1
 800307a:	0000      	movs	r0, r0
 800307c:	0324      	lsls	r4, r4, #12
 800307e:	0300      	lsls	r0, r0, #12
 8003080:	b510      	push	{r4, lr}
 8003082:	4a07      	ldr	r2, [pc, #28]	@ (0x80030a0)
 8003084:	2103      	movs	r1, #3
 8003086:	7011      	strb	r1, [r2, #0]
 8003088:	4c06      	ldr	r4, [pc, #24]	@ (0x80030a4)
 800308a:	2110      	movs	r1, #16
 800308c:	7021      	strb	r1, [r4, #0]
 800308e:	f7ff fefd 	bl	0x8002e8c
 8003092:	0600      	lsls	r0, r0, #24
 8003094:	0e00      	lsrs	r0, r0, #24
 8003096:	2116      	movs	r1, #22
 8003098:	7021      	strb	r1, [r4, #0]
 800309a:	bc10      	pop	{r4}
 800309c:	bc02      	pop	{r1}
 800309e:	4708      	bx	r1
 80030a0:	0324      	lsls	r4, r4, #12
 80030a2:	0300      	lsls	r0, r0, #12
 80030a4:	0325      	lsls	r5, r4, #12
 80030a6:	0300      	lsls	r0, r0, #12
 80030a8:	b510      	push	{r4, lr}
 80030aa:	b081      	sub	sp, #4
 80030ac:	1c04      	adds	r4, r0, #0
 80030ae:	9803      	ldr	r0, [sp, #12]
 80030b0:	0412      	lsls	r2, r2, #16
 80030b2:	0c12      	lsrs	r2, r2, #16
 80030b4:	061b      	lsls	r3, r3, #24
 80030b6:	0e1b      	lsrs	r3, r3, #24
 80030b8:	0600      	lsls	r0, r0, #24
 80030ba:	0e00      	lsrs	r0, r0, #24
 80030bc:	9000      	str	r0, [sp, #0]
 80030be:	1c20      	adds	r0, r4, #0
 80030c0:	f7ff fe1c 	bl	0x8002cfc
 80030c4:	1c20      	adds	r0, r4, #0
 80030c6:	f7ff fe8f 	bl	0x8002de8
 80030ca:	0600      	lsls	r0, r0, #24
 80030cc:	0e00      	lsrs	r0, r0, #24
 80030ce:	b001      	add	sp, #4
 80030d0:	bc10      	pop	{r4}
 80030d2:	bc02      	pop	{r1}
 80030d4:	4708      	bx	r1
 80030d6:	0000      	movs	r0, r0
 80030d8:	b530      	push	{r4, r5, lr}
 80030da:	b082      	sub	sp, #8
 80030dc:	1c05      	adds	r5, r0, #0
 80030de:	9c05      	ldr	r4, [sp, #20]
 80030e0:	0412      	lsls	r2, r2, #16
 80030e2:	0c12      	lsrs	r2, r2, #16
 80030e4:	061b      	lsls	r3, r3, #24
 80030e6:	0e1b      	lsrs	r3, r3, #24
 80030e8:	0624      	lsls	r4, r4, #24
 80030ea:	0e24      	lsrs	r4, r4, #24
 80030ec:	a801      	add	r0, sp, #4
 80030ee:	7001      	strb	r1, [r0, #0]
 80030f0:	1c01      	adds	r1, r0, #0
 80030f2:	20ff      	movs	r0, #255	@ 0xff
 80030f4:	7048      	strb	r0, [r1, #1]
 80030f6:	9400      	str	r4, [sp, #0]
 80030f8:	1c28      	adds	r0, r5, #0
 80030fa:	f7ff fdb5 	bl	0x8002c68
 80030fe:	1c28      	adds	r0, r5, #0
 8003100:	f000 f8fa 	bl	0x80032f8
 8003104:	0600      	lsls	r0, r0, #24
 8003106:	0e00      	lsrs	r0, r0, #24
 8003108:	b002      	add	sp, #8
 800310a:	bc30      	pop	{r4, r5}
 800310c:	bc02      	pop	{r1}
 800310e:	4708      	bx	r1
 8003110:	b510      	push	{r4, lr}
 8003112:	1c03      	adds	r3, r0, #0
 8003114:	8a99      	ldrh	r1, [r3, #20]
 8003116:	1c48      	adds	r0, r1, #1
 8003118:	8298      	strh	r0, [r3, #20]
 800311a:	0409      	lsls	r1, r1, #16
 800311c:	0c09      	lsrs	r1, r1, #16
 800311e:	6918      	ldr	r0, [r3, #16]
 8003120:	1840      	adds	r0, r0, r1
 8003122:	7800      	ldrb	r0, [r0, #0]
 8003124:	3801      	subs	r0, #1
 8003126:	280f      	cmp	r0, #15
 8003128:	d900      	bls.n	0x800312c
 800312a:	e0e0      	b.n	0x80032ee
 800312c:	0080      	lsls	r0, r0, #2
 800312e:	4902      	ldr	r1, [pc, #8]	@ (0x8003138)
 8003130:	1840      	adds	r0, r0, r1
 8003132:	6800      	ldr	r0, [r0, #0]
 8003134:	4687      	mov	pc, r0
 8003136:	0000      	movs	r0, r0
 8003138:	313c      	adds	r1, #60	@ 0x3c
 800313a:	0800      	lsrs	r0, r0, #32
 800313c:	317c      	adds	r1, #124	@ 0x7c
 800313e:	0800      	lsrs	r0, r0, #32
 8003140:	3190      	adds	r1, #144	@ 0x90
 8003142:	0800      	lsrs	r0, r0, #32
 8003144:	31a4      	adds	r1, #164	@ 0xa4
 8003146:	0800      	lsrs	r0, r0, #32
 8003148:	31b8      	adds	r1, #184	@ 0xb8
 800314a:	0800      	lsrs	r0, r0, #32
 800314c:	31e8      	adds	r1, #232	@ 0xe8
 800314e:	0800      	lsrs	r0, r0, #32
 8003150:	31fc      	adds	r1, #252	@ 0xfc
 8003152:	0800      	lsrs	r0, r0, #32
 8003154:	3210      	adds	r2, #16
 8003156:	0800      	lsrs	r0, r0, #32
 8003158:	3218      	adds	r2, #24
 800315a:	0800      	lsrs	r0, r0, #32
 800315c:	3230      	adds	r2, #48	@ 0x30
 800315e:	0800      	lsrs	r0, r0, #32
 8003160:	3236      	adds	r2, #54	@ 0x36
 8003162:	0800      	lsrs	r0, r0, #32
 8003164:	323c      	adds	r2, #60	@ 0x3c
 8003166:	0800      	lsrs	r0, r0, #32
 8003168:	328c      	adds	r2, #140	@ 0x8c
 800316a:	0800      	lsrs	r0, r0, #32
 800316c:	32b4      	adds	r2, #180	@ 0xb4
 800316e:	0800      	lsrs	r0, r0, #32
 8003170:	32ce      	adds	r2, #206	@ 0xce
 8003172:	0800      	lsrs	r0, r0, #32
 8003174:	32e8      	adds	r2, #232	@ 0xe8
 8003176:	0800      	lsrs	r0, r0, #32
 8003178:	3264      	adds	r2, #100	@ 0x64
 800317a:	0800      	lsrs	r0, r0, #32
 800317c:	8a99      	ldrh	r1, [r3, #20]
 800317e:	1c48      	adds	r0, r1, #1
 8003180:	8298      	strh	r0, [r3, #20]
 8003182:	0409      	lsls	r1, r1, #16
 8003184:	0c09      	lsrs	r1, r1, #16
 8003186:	6918      	ldr	r0, [r3, #16]
 8003188:	1840      	adds	r0, r0, r1
 800318a:	7800      	ldrb	r0, [r0, #0]
 800318c:	7318      	strb	r0, [r3, #12]
 800318e:	e0ae      	b.n	0x80032ee
 8003190:	8a99      	ldrh	r1, [r3, #20]
 8003192:	1c48      	adds	r0, r1, #1
 8003194:	8298      	strh	r0, [r3, #20]
 8003196:	0409      	lsls	r1, r1, #16
 8003198:	0c09      	lsrs	r1, r1, #16
 800319a:	6918      	ldr	r0, [r3, #16]
 800319c:	1840      	adds	r0, r0, r1
 800319e:	7800      	ldrb	r0, [r0, #0]
 80031a0:	7358      	strb	r0, [r3, #13]
 80031a2:	e0a4      	b.n	0x80032ee
 80031a4:	8a99      	ldrh	r1, [r3, #20]
 80031a6:	1c48      	adds	r0, r1, #1
 80031a8:	8298      	strh	r0, [r3, #20]
 80031aa:	0409      	lsls	r1, r1, #16
 80031ac:	0c09      	lsrs	r1, r1, #16
 80031ae:	6918      	ldr	r0, [r3, #16]
 80031b0:	1840      	adds	r0, r0, r1
 80031b2:	7800      	ldrb	r0, [r0, #0]
 80031b4:	7398      	strb	r0, [r3, #14]
 80031b6:	e09a      	b.n	0x80032ee
 80031b8:	8a98      	ldrh	r0, [r3, #20]
 80031ba:	1c41      	adds	r1, r0, #1
 80031bc:	8299      	strh	r1, [r3, #20]
 80031be:	0400      	lsls	r0, r0, #16
 80031c0:	0c00      	lsrs	r0, r0, #16
 80031c2:	691a      	ldr	r2, [r3, #16]
 80031c4:	1810      	adds	r0, r2, r0
 80031c6:	7800      	ldrb	r0, [r0, #0]
 80031c8:	7318      	strb	r0, [r3, #12]
 80031ca:	1c48      	adds	r0, r1, #1
 80031cc:	8298      	strh	r0, [r3, #20]
 80031ce:	0409      	lsls	r1, r1, #16
 80031d0:	0c09      	lsrs	r1, r1, #16
 80031d2:	1851      	adds	r1, r2, r1
 80031d4:	7809      	ldrb	r1, [r1, #0]
 80031d6:	7359      	strb	r1, [r3, #13]
 80031d8:	1c41      	adds	r1, r0, #1
 80031da:	8299      	strh	r1, [r3, #20]
 80031dc:	0400      	lsls	r0, r0, #16
 80031de:	0c00      	lsrs	r0, r0, #16
 80031e0:	1812      	adds	r2, r2, r0
 80031e2:	7810      	ldrb	r0, [r2, #0]
 80031e4:	7398      	strb	r0, [r3, #14]
 80031e6:	e082      	b.n	0x80032ee
 80031e8:	8a99      	ldrh	r1, [r3, #20]
 80031ea:	1c48      	adds	r0, r1, #1
 80031ec:	8298      	strh	r0, [r3, #20]
 80031ee:	0409      	lsls	r1, r1, #16
 80031f0:	0c09      	lsrs	r1, r1, #16
 80031f2:	6918      	ldr	r0, [r3, #16]
 80031f4:	1840      	adds	r0, r0, r1
 80031f6:	7800      	ldrb	r0, [r0, #0]
 80031f8:	73d8      	strb	r0, [r3, #15]
 80031fa:	e078      	b.n	0x80032ee
 80031fc:	8a99      	ldrh	r1, [r3, #20]
 80031fe:	1c48      	adds	r0, r1, #1
 8003200:	8298      	strh	r0, [r3, #20]
 8003202:	0409      	lsls	r1, r1, #16
 8003204:	0c09      	lsrs	r1, r1, #16
 8003206:	6918      	ldr	r0, [r3, #16]
 8003208:	1840      	adds	r0, r0, r1
 800320a:	7800      	ldrb	r0, [r0, #0]
 800320c:	72d8      	strb	r0, [r3, #11]
 800320e:	e06e      	b.n	0x80032ee
 8003210:	6818      	ldr	r0, [r3, #0]
 8003212:	7a00      	ldrb	r0, [r0, #8]
 8003214:	72d8      	strb	r0, [r3, #11]
 8003216:	e06a      	b.n	0x80032ee
 8003218:	2004      	movs	r0, #4
 800321a:	8098      	strh	r0, [r3, #4]
 800321c:	8a99      	ldrh	r1, [r3, #20]
 800321e:	1c48      	adds	r0, r1, #1
 8003220:	8298      	strh	r0, [r3, #20]
 8003222:	0409      	lsls	r1, r1, #16
 8003224:	0c09      	lsrs	r1, r1, #16
 8003226:	6918      	ldr	r0, [r3, #16]
 8003228:	1840      	adds	r0, r0, r1
 800322a:	7800      	ldrb	r0, [r0, #0]
 800322c:	7258      	strb	r0, [r3, #9]
 800322e:	e05e      	b.n	0x80032ee
 8003230:	2005      	movs	r0, #5
 8003232:	8098      	strh	r0, [r3, #4]
 8003234:	e05b      	b.n	0x80032ee
 8003236:	200a      	movs	r0, #10
 8003238:	8098      	strh	r0, [r3, #4]
 800323a:	e058      	b.n	0x80032ee
 800323c:	8a98      	ldrh	r0, [r3, #20]
 800323e:	1c41      	adds	r1, r0, #1
 8003240:	8299      	strh	r1, [r3, #20]
 8003242:	0400      	lsls	r0, r0, #16
 8003244:	0c00      	lsrs	r0, r0, #16
 8003246:	691a      	ldr	r2, [r3, #16]
 8003248:	1810      	adds	r0, r2, r0
 800324a:	7804      	ldrb	r4, [r0, #0]
 800324c:	1c48      	adds	r0, r1, #1
 800324e:	8298      	strh	r0, [r3, #20]
 8003250:	0409      	lsls	r1, r1, #16
 8003252:	0c09      	lsrs	r1, r1, #16
 8003254:	1852      	adds	r2, r2, r1
 8003256:	7810      	ldrb	r0, [r2, #0]
 8003258:	0200      	lsls	r0, r0, #8
 800325a:	4304      	orrs	r4, r0
 800325c:	1c20      	adds	r0, r4, #0
 800325e:	f06f f925 	bl	0x80724ac
 8003262:	e044      	b.n	0x80032ee
 8003264:	8a98      	ldrh	r0, [r3, #20]
 8003266:	1c41      	adds	r1, r0, #1
 8003268:	8299      	strh	r1, [r3, #20]
 800326a:	0400      	lsls	r0, r0, #16
 800326c:	0c00      	lsrs	r0, r0, #16
 800326e:	691a      	ldr	r2, [r3, #16]
 8003270:	1810      	adds	r0, r2, r0
 8003272:	7804      	ldrb	r4, [r0, #0]
 8003274:	1c48      	adds	r0, r1, #1
 8003276:	8298      	strh	r0, [r3, #20]
 8003278:	0409      	lsls	r1, r1, #16
 800327a:	0c09      	lsrs	r1, r1, #16
 800327c:	1852      	adds	r2, r2, r1
 800327e:	7810      	ldrb	r0, [r2, #0]
 8003280:	0200      	lsls	r0, r0, #8
 8003282:	4304      	orrs	r4, r0
 8003284:	1c20      	adds	r0, r4, #0
 8003286:	f06f f921 	bl	0x80724cc
 800328a:	e030      	b.n	0x80032ee
 800328c:	4808      	ldr	r0, [pc, #32]	@ (0x80032b0)
 800328e:	7a9a      	ldrb	r2, [r3, #10]
 8003290:	0092      	lsls	r2, r2, #2
 8003292:	1812      	adds	r2, r2, r0
 8003294:	8a99      	ldrh	r1, [r3, #20]
 8003296:	1c48      	adds	r0, r1, #1
 8003298:	8298      	strh	r0, [r3, #20]
 800329a:	0409      	lsls	r1, r1, #16
 800329c:	0c09      	lsrs	r1, r1, #16
 800329e:	6918      	ldr	r0, [r3, #16]
 80032a0:	1840      	adds	r0, r0, r1
 80032a2:	7801      	ldrb	r1, [r0, #0]
 80032a4:	6812      	ldr	r2, [r2, #0]
 80032a6:	1c18      	adds	r0, r3, #0
 80032a8:	f1ae f818 	bl	0x81b12dc
 80032ac:	2001      	movs	r0, #1
 80032ae:	e01f      	b.n	0x80032f0
 80032b0:	b3ac      	cbz	r4, 0x800331e
 80032b2:	081b      	lsrs	r3, r3, #32
 80032b4:	8a99      	ldrh	r1, [r3, #20]
 80032b6:	1c48      	adds	r0, r1, #1
 80032b8:	8298      	strh	r0, [r3, #20]
 80032ba:	0409      	lsls	r1, r1, #16
 80032bc:	0c09      	lsrs	r1, r1, #16
 80032be:	6918      	ldr	r0, [r3, #16]
 80032c0:	1840      	adds	r0, r0, r1
 80032c2:	7800      	ldrb	r0, [r0, #0]
 80032c4:	7ed9      	ldrb	r1, [r3, #27]
 80032c6:	1840      	adds	r0, r0, r1
 80032c8:	76d8      	strb	r0, [r3, #27]
 80032ca:	2001      	movs	r0, #1
 80032cc:	e010      	b.n	0x80032f0
 80032ce:	8a99      	ldrh	r1, [r3, #20]
 80032d0:	1c48      	adds	r0, r1, #1
 80032d2:	8298      	strh	r0, [r3, #20]
 80032d4:	0409      	lsls	r1, r1, #16
 80032d6:	0c09      	lsrs	r1, r1, #16
 80032d8:	6918      	ldr	r0, [r3, #16]
 80032da:	1840      	adds	r0, r0, r1
 80032dc:	7800      	ldrb	r0, [r0, #0]
 80032de:	7f59      	ldrb	r1, [r3, #29]
 80032e0:	1840      	adds	r0, r0, r1
 80032e2:	7758      	strb	r0, [r3, #29]
 80032e4:	2001      	movs	r0, #1
 80032e6:	e003      	b.n	0x80032f0
 80032e8:	1c18      	adds	r0, r3, #0
 80032ea:	f000 fc5d 	bl	0x8003ba8
 80032ee:	2002      	movs	r0, #2
 80032f0:	bc10      	pop	{r4}
 80032f2:	bc02      	pop	{r1}
 80032f4:	4708      	bx	r1
 80032f6:	0000      	movs	r0, r0
 80032f8:	b510      	push	{r4, lr}
 80032fa:	1c04      	adds	r4, r0, #0
 80032fc:	8aa0      	ldrh	r0, [r4, #20]
 80032fe:	1c41      	adds	r1, r0, #1
 8003300:	82a1      	strh	r1, [r4, #20]
 8003302:	0400      	lsls	r0, r0, #16
 8003304:	0c00      	lsrs	r0, r0, #16
 8003306:	6921      	ldr	r1, [r4, #16]
 8003308:	1809      	adds	r1, r1, r0
 800330a:	780b      	ldrb	r3, [r1, #0]
 800330c:	1c18      	adds	r0, r3, #0
 800330e:	38fa      	subs	r0, #250	@ 0xfa
 8003310:	2805      	cmp	r0, #5
 8003312:	d82c      	bhi.n	0x800336e
 8003314:	0080      	lsls	r0, r0, #2
 8003316:	4902      	ldr	r1, [pc, #8]	@ (0x8003320)
 8003318:	1840      	adds	r0, r0, r1
 800331a:	6800      	ldr	r0, [r0, #0]
 800331c:	4687      	mov	pc, r0
 800331e:	0000      	movs	r0, r0
 8003320:	3324      	adds	r3, #36	@ 0x24
 8003322:	0800      	lsrs	r0, r0, #32
 8003324:	3354      	adds	r3, #84	@ 0x54
 8003326:	0800      	lsrs	r0, r0, #32
 8003328:	334a      	adds	r3, #74	@ 0x4a
 800332a:	0800      	lsrs	r0, r0, #32
 800332c:	3362      	adds	r3, #98	@ 0x62
 800332e:	0800      	lsrs	r0, r0, #32
 8003330:	3342      	adds	r3, #66	@ 0x42
 8003332:	0800      	lsrs	r0, r0, #32
 8003334:	3346      	adds	r3, #70	@ 0x46
 8003336:	0800      	lsrs	r0, r0, #32
 8003338:	333c      	adds	r3, #60	@ 0x3c
 800333a:	0800      	lsrs	r0, r0, #32
 800333c:	2000      	movs	r0, #0
 800333e:	80a0      	strh	r0, [r4, #4]
 8003340:	e01f      	b.n	0x8003382
 8003342:	2007      	movs	r0, #7
 8003344:	e00a      	b.n	0x800335c
 8003346:	2006      	movs	r0, #6
 8003348:	e008      	b.n	0x800335c
 800334a:	1c20      	adds	r0, r4, #0
 800334c:	f000 fdfe 	bl	0x8003f4c
 8003350:	2008      	movs	r0, #8
 8003352:	e003      	b.n	0x800335c
 8003354:	1c20      	adds	r0, r4, #0
 8003356:	f000 fdf9 	bl	0x8003f4c
 800335a:	2009      	movs	r0, #9
 800335c:	80a0      	strh	r0, [r4, #4]
 800335e:	2002      	movs	r0, #2
 8003360:	e00f      	b.n	0x8003382
 8003362:	1c20      	adds	r0, r4, #0
 8003364:	f7ff fed4 	bl	0x8003110
 8003368:	0600      	lsls	r0, r0, #24
 800336a:	0e00      	lsrs	r0, r0, #24
 800336c:	e009      	b.n	0x8003382
 800336e:	4806      	ldr	r0, [pc, #24]	@ (0x8003388)
 8003370:	7aa1      	ldrb	r1, [r4, #10]
 8003372:	0089      	lsls	r1, r1, #2
 8003374:	1809      	adds	r1, r1, r0
 8003376:	680a      	ldr	r2, [r1, #0]
 8003378:	1c20      	adds	r0, r4, #0
 800337a:	1c19      	adds	r1, r3, #0
 800337c:	f1ad ffae 	bl	0x81b12dc
 8003380:	2001      	movs	r0, #1
 8003382:	bc10      	pop	{r4}
 8003384:	bc02      	pop	{r1}
 8003386:	4708      	bx	r1
 8003388:	b3ac      	cbz	r4, 0x80033f6
 800338a:	081b      	lsrs	r3, r3, #32
 800338c:	b530      	push	{r4, r5, lr}
 800338e:	b082      	sub	sp, #8
 8003390:	1c05      	adds	r5, r0, #0
 8003392:	1c08      	adds	r0, r1, #0
 8003394:	6a29      	ldr	r1, [r5, #32]
 8003396:	7aea      	ldrb	r2, [r5, #11]
 8003398:	7b2b      	ldrb	r3, [r5, #12]
 800339a:	7b6c      	ldrb	r4, [r5, #13]
 800339c:	9400      	str	r4, [sp, #0]
 800339e:	7bac      	ldrb	r4, [r5, #14]
 80033a0:	9401      	str	r4, [sp, #4]
 80033a2:	f000 f945 	bl	0x8003630
 80033a6:	6a28      	ldr	r0, [r5, #32]
 80033a8:	3040      	adds	r0, #64	@ 0x40
 80033aa:	6228      	str	r0, [r5, #32]
 80033ac:	b002      	add	sp, #8
 80033ae:	bc30      	pop	{r4, r5}
 80033b0:	bc01      	pop	{r0}
 80033b2:	4700      	bx	r0
 80033b4:	b5f0      	push	{r4, r5, r6, r7, lr}
 80033b6:	464f      	mov	r7, r9
 80033b8:	4646      	mov	r6, r8
 80033ba:	b4c0      	push	{r6, r7}
 80033bc:	b083      	sub	sp, #12
 80033be:	1c04      	adds	r4, r0, #0
 80033c0:	4688      	mov	r8, r1
 80033c2:	980a      	ldr	r0, [sp, #40]	@ 0x28
 80033c4:	990b      	ldr	r1, [sp, #44]	@ 0x2c
 80033c6:	0612      	lsls	r2, r2, #24
 80033c8:	0e15      	lsrs	r5, r2, #24
 80033ca:	061b      	lsls	r3, r3, #24
 80033cc:	0e1f      	lsrs	r7, r3, #24
 80033ce:	0600      	lsls	r0, r0, #24
 80033d0:	0e06      	lsrs	r6, r0, #24
 80033d2:	0609      	lsls	r1, r1, #24
 80033d4:	0e09      	lsrs	r1, r1, #24
 80033d6:	4689      	mov	r9, r1
 80033d8:	0424      	lsls	r4, r4, #16
 80033da:	0c24      	lsrs	r4, r4, #16
 80033dc:	ab02      	add	r3, sp, #8
 80033de:	1c28      	adds	r0, r5, #0
 80033e0:	1c21      	adds	r1, r4, #0
 80033e2:	aa01      	add	r2, sp, #4
 80033e4:	f000 f9a4 	bl	0x8003730
 80033e8:	2d06      	cmp	r5, #6
 80033ea:	d834      	bhi.n	0x8003456
 80033ec:	00a8      	lsls	r0, r5, #2
 80033ee:	4902      	ldr	r1, [pc, #8]	@ (0x80033f8)
 80033f0:	1840      	adds	r0, r0, r1
 80033f2:	6800      	ldr	r0, [r0, #0]
 80033f4:	4687      	mov	pc, r0
 80033f6:	0000      	movs	r0, r0
 80033f8:	33fc      	adds	r3, #252	@ 0xfc
 80033fa:	0800      	lsrs	r0, r0, #32
 80033fc:	3418      	adds	r4, #24
 80033fe:	0800      	lsrs	r0, r0, #32
 8003400:	3418      	adds	r4, #24
 8003402:	0800      	lsrs	r0, r0, #32
 8003404:	3418      	adds	r4, #24
 8003406:	0800      	lsrs	r0, r0, #32
 8003408:	3436      	adds	r4, #54	@ 0x36
 800340a:	0800      	lsrs	r0, r0, #32
 800340c:	3436      	adds	r4, #54	@ 0x36
 800340e:	0800      	lsrs	r0, r0, #32
 8003410:	3436      	adds	r4, #54	@ 0x36
 8003412:	0800      	lsrs	r0, r0, #32
 8003414:	3418      	adds	r4, #24
 8003416:	0800      	lsrs	r0, r0, #32
 8003418:	9801      	ldr	r0, [sp, #4]
 800341a:	4641      	mov	r1, r8
 800341c:	1c3a      	adds	r2, r7, #0
 800341e:	1c33      	adds	r3, r6, #0
 8003420:	f000 fa06 	bl	0x8003830
 8003424:	9802      	ldr	r0, [sp, #8]
 8003426:	21f0      	movs	r1, #240	@ 0xf0
 8003428:	0089      	lsls	r1, r1, #2
 800342a:	4441      	add	r1, r8
 800342c:	1c3a      	adds	r2, r7, #0
 800342e:	1c33      	adds	r3, r6, #0
 8003430:	f000 f9fe 	bl	0x8003830
 8003434:	e00f      	b.n	0x8003456
 8003436:	9801      	ldr	r0, [sp, #4]
 8003438:	9600      	str	r6, [sp, #0]
 800343a:	4641      	mov	r1, r8
 800343c:	1c3a      	adds	r2, r7, #0
 800343e:	464b      	mov	r3, r9
 8003440:	f000 fa2e 	bl	0x80038a0
 8003444:	9802      	ldr	r0, [sp, #8]
 8003446:	21f0      	movs	r1, #240	@ 0xf0
 8003448:	0089      	lsls	r1, r1, #2
 800344a:	4441      	add	r1, r8
 800344c:	9600      	str	r6, [sp, #0]
 800344e:	1c3a      	adds	r2, r7, #0
 8003450:	464b      	mov	r3, r9
 8003452:	f000 fa25 	bl	0x80038a0
 8003456:	b003      	add	sp, #12
 8003458:	bc18      	pop	{r3, r4}
 800345a:	4698      	mov	r8, r3
 800345c:	46a1      	mov	r9, r4
 800345e:	bcf0      	pop	{r4, r5, r6, r7}
 8003460:	bc01      	pop	{r0}
 8003462:	4700      	bx	r0
 8003464:	b530      	push	{r4, r5, lr}
 8003466:	b083      	sub	sp, #12
 8003468:	1c04      	adds	r4, r0, #0
 800346a:	1c0d      	adds	r5, r1, #0
 800346c:	f000 f838 	bl	0x80034e0
 8003470:	9002      	str	r0, [sp, #8]
 8003472:	7ae2      	ldrb	r2, [r4, #11]
 8003474:	7b23      	ldrb	r3, [r4, #12]
 8003476:	7b60      	ldrb	r0, [r4, #13]
 8003478:	9000      	str	r0, [sp, #0]
 800347a:	7ba0      	ldrb	r0, [r4, #14]
 800347c:	9001      	str	r0, [sp, #4]
 800347e:	1c28      	adds	r0, r5, #0
 8003480:	9902      	ldr	r1, [sp, #8]
 8003482:	f7ff ff97 	bl	0x80033b4
 8003486:	1c20      	adds	r0, r4, #0
 8003488:	f000 f80e 	bl	0x80034a8
 800348c:	b003      	add	sp, #12
 800348e:	bc30      	pop	{r4, r5}
 8003490:	bc01      	pop	{r0}
 8003492:	4700      	bx	r0
 8003494:	b510      	push	{r4, lr}
 8003496:	1c04      	adds	r4, r0, #0
 8003498:	f7ff ffe4 	bl	0x8003464
 800349c:	7ee0      	ldrb	r0, [r4, #27]
 800349e:	3001      	adds	r0, #1
 80034a0:	76e0      	strb	r0, [r4, #27]
 80034a2:	bc10      	pop	{r4}
 80034a4:	bc01      	pop	{r0}
 80034a6:	4700      	bx	r0
 80034a8:	b510      	push	{r4, lr}
 80034aa:	7e81      	ldrb	r1, [r0, #26]
 80034ac:	3102      	adds	r1, #2
 80034ae:	8ac2      	ldrh	r2, [r0, #22]
 80034b0:	1889      	adds	r1, r1, r2
 80034b2:	7ec2      	ldrb	r2, [r0, #27]
 80034b4:	1852      	adds	r2, r2, r1
 80034b6:	7f04      	ldrb	r4, [r0, #28]
 80034b8:	7f41      	ldrb	r1, [r0, #29]
 80034ba:	1864      	adds	r4, r4, r1
 80034bc:	0121      	lsls	r1, r4, #4
 80034be:	1b09      	subs	r1, r1, r4
 80034c0:	0049      	lsls	r1, r1, #1
 80034c2:	1851      	adds	r1, r2, r1
 80034c4:	0409      	lsls	r1, r1, #16
 80034c6:	0c09      	lsrs	r1, r1, #16
 80034c8:	3401      	adds	r4, #1
 80034ca:	0123      	lsls	r3, r4, #4
 80034cc:	1b1b      	subs	r3, r3, r4
 80034ce:	005b      	lsls	r3, r3, #1
 80034d0:	18d2      	adds	r2, r2, r3
 80034d2:	0412      	lsls	r2, r2, #16
 80034d4:	0c12      	lsrs	r2, r2, #16
 80034d6:	f000 f901 	bl	0x80036dc
 80034da:	bc10      	pop	{r4}
 80034dc:	bc01      	pop	{r0}
 80034de:	4700      	bx	r0
 80034e0:	b500      	push	{lr}
 80034e2:	7e81      	ldrb	r1, [r0, #26]
 80034e4:	7ec2      	ldrb	r2, [r0, #27]
 80034e6:	1889      	adds	r1, r1, r2
 80034e8:	7f02      	ldrb	r2, [r0, #28]
 80034ea:	7f43      	ldrb	r3, [r0, #29]
 80034ec:	18d2      	adds	r2, r2, r3
 80034ee:	0609      	lsls	r1, r1, #24
 80034f0:	0e09      	lsrs	r1, r1, #24
 80034f2:	0612      	lsls	r2, r2, #24
 80034f4:	0e12      	lsrs	r2, r2, #24
 80034f6:	f000 f803 	bl	0x8003500
 80034fa:	bc02      	pop	{r1}
 80034fc:	4708      	bx	r1
 80034fe:	0000      	movs	r0, r0
 8003500:	0609      	lsls	r1, r1, #24
 8003502:	0e09      	lsrs	r1, r1, #24
 8003504:	0612      	lsls	r2, r2, #24
 8003506:	0e12      	lsrs	r2, r2, #24
 8003508:	6803      	ldr	r3, [r0, #0]
 800350a:	3102      	adds	r1, #2
 800350c:	8ac0      	ldrh	r0, [r0, #22]
 800350e:	1809      	adds	r1, r1, r0
 8003510:	0110      	lsls	r0, r2, #4
 8003512:	1a80      	subs	r0, r0, r2
 8003514:	0040      	lsls	r0, r0, #1
 8003516:	1809      	adds	r1, r1, r0
 8003518:	0149      	lsls	r1, r1, #5
 800351a:	68d8      	ldr	r0, [r3, #12]
 800351c:	1840      	adds	r0, r0, r1
 800351e:	4770      	bx	lr
 8003520:	b530      	push	{r4, r5, lr}
 8003522:	b082      	sub	sp, #8
 8003524:	1c05      	adds	r5, r0, #0
 8003526:	1c08      	adds	r0, r1, #0
 8003528:	682b      	ldr	r3, [r5, #0]
 800352a:	8aea      	ldrh	r2, [r5, #22]
 800352c:	8b29      	ldrh	r1, [r5, #24]
 800352e:	1852      	adds	r2, r2, r1
 8003530:	0152      	lsls	r2, r2, #5
 8003532:	68d9      	ldr	r1, [r3, #12]
 8003534:	1889      	adds	r1, r1, r2
 8003536:	7aea      	ldrb	r2, [r5, #11]
 8003538:	7b2b      	ldrb	r3, [r5, #12]
 800353a:	7b6c      	ldrb	r4, [r5, #13]
 800353c:	9400      	str	r4, [sp, #0]
 800353e:	7bac      	ldrb	r4, [r5, #14]
 8003540:	9401      	str	r4, [sp, #4]
 8003542:	f000 f875 	bl	0x8003630
 8003546:	8b2a      	ldrh	r2, [r5, #24]
 8003548:	8ae8      	ldrh	r0, [r5, #22]
 800354a:	1812      	adds	r2, r2, r0
 800354c:	0412      	lsls	r2, r2, #16
 800354e:	0c11      	lsrs	r1, r2, #16
 8003550:	2080      	movs	r0, #128	@ 0x80
 8003552:	0240      	lsls	r0, r0, #9
 8003554:	1812      	adds	r2, r2, r0
 8003556:	0c12      	lsrs	r2, r2, #16
 8003558:	1c28      	adds	r0, r5, #0
 800355a:	f000 f8bf 	bl	0x80036dc
 800355e:	b002      	add	sp, #8
 8003560:	bc30      	pop	{r4, r5}
 8003562:	bc01      	pop	{r0}
 8003564:	4700      	bx	r0
 8003566:	0000      	movs	r0, r0
 8003568:	b510      	push	{r4, lr}
 800356a:	1c04      	adds	r4, r0, #0
 800356c:	f7ff ffd8 	bl	0x8003520
 8003570:	8b20      	ldrh	r0, [r4, #24]
 8003572:	3002      	adds	r0, #2
 8003574:	8320      	strh	r0, [r4, #24]
 8003576:	7ee0      	ldrb	r0, [r4, #27]
 8003578:	3001      	adds	r0, #1
 800357a:	76e0      	strb	r0, [r4, #27]
 800357c:	bc10      	pop	{r4}
 800357e:	bc01      	pop	{r0}
 8003580:	4700      	bx	r0
 8003582:	0000      	movs	r0, r0
 8003584:	b500      	push	{lr}
 8003586:	004a      	lsls	r2, r1, #1
 8003588:	8ac1      	ldrh	r1, [r0, #22]
 800358a:	1852      	adds	r2, r2, r1
 800358c:	0412      	lsls	r2, r2, #16
 800358e:	0c11      	lsrs	r1, r2, #16
 8003590:	2380      	movs	r3, #128	@ 0x80
 8003592:	025b      	lsls	r3, r3, #9
 8003594:	18d2      	adds	r2, r2, r3
 8003596:	0c12      	lsrs	r2, r2, #16
 8003598:	f000 f8a0 	bl	0x80036dc
 800359c:	bc01      	pop	{r0}
 800359e:	4700      	bx	r0
 80035a0:	b500      	push	{lr}
 80035a2:	1c0b      	adds	r3, r1, #0
 80035a4:	4907      	ldr	r1, [pc, #28]	@ (0x80035c4)
 80035a6:	009b      	lsls	r3, r3, #2
 80035a8:	185b      	adds	r3, r3, r1
 80035aa:	7819      	ldrb	r1, [r3, #0]
 80035ac:	8ac2      	ldrh	r2, [r0, #22]
 80035ae:	1851      	adds	r1, r2, r1
 80035b0:	0409      	lsls	r1, r1, #16
 80035b2:	0c09      	lsrs	r1, r1, #16
 80035b4:	785b      	ldrb	r3, [r3, #1]
 80035b6:	18d2      	adds	r2, r2, r3
 80035b8:	0412      	lsls	r2, r2, #16
 80035ba:	0c12      	lsrs	r2, r2, #16
 80035bc:	f000 f88e 	bl	0x80036dc
 80035c0:	bc01      	pop	{r0}
 80035c2:	4700      	bx	r0
 80035c4:	34a8      	adds	r4, #168	@ 0xa8
 80035c6:	081b      	lsrs	r3, r3, #32
 80035c8:	b500      	push	{lr}
 80035ca:	1c0b      	adds	r3, r1, #0
 80035cc:	8ac2      	ldrh	r2, [r0, #22]
 80035ce:	1c11      	adds	r1, r2, #0
 80035d0:	31d4      	adds	r1, #212	@ 0xd4
 80035d2:	0409      	lsls	r1, r1, #16
 80035d4:	0c09      	lsrs	r1, r1, #16
 80035d6:	18d2      	adds	r2, r2, r3
 80035d8:	0412      	lsls	r2, r2, #16
 80035da:	0c12      	lsrs	r2, r2, #16
 80035dc:	f000 f87e 	bl	0x80036dc
 80035e0:	bc01      	pop	{r0}
 80035e2:	4700      	bx	r0
 80035e4:	b500      	push	{lr}
 80035e6:	1c0b      	adds	r3, r1, #0
 80035e8:	4907      	ldr	r1, [pc, #28]	@ (0x8003608)
 80035ea:	009b      	lsls	r3, r3, #2
 80035ec:	185b      	adds	r3, r3, r1
 80035ee:	7819      	ldrb	r1, [r3, #0]
 80035f0:	8ac2      	ldrh	r2, [r0, #22]
 80035f2:	1851      	adds	r1, r2, r1
 80035f4:	0409      	lsls	r1, r1, #16
 80035f6:	0c09      	lsrs	r1, r1, #16
 80035f8:	785b      	ldrb	r3, [r3, #1]
 80035fa:	18d2      	adds	r2, r2, r3
 80035fc:	0412      	lsls	r2, r2, #16
 80035fe:	0c12      	lsrs	r2, r2, #16
 8003600:	f000 f86c 	bl	0x80036dc
 8003604:	bc01      	pop	{r0}
 8003606:	4700      	bx	r0
 8003608:	3884      	subs	r0, #132	@ 0x84
 800360a:	081b      	lsrs	r3, r3, #32
 800360c:	b510      	push	{r4, lr}
 800360e:	1c04      	adds	r4, r0, #0
 8003610:	4a06      	ldr	r2, [pc, #24]	@ (0x800362c)
 8003612:	7ae0      	ldrb	r0, [r4, #11]
 8003614:	0080      	lsls	r0, r0, #2
 8003616:	1880      	adds	r0, r0, r2
 8003618:	6802      	ldr	r2, [r0, #0]
 800361a:	1c20      	adds	r0, r4, #0
 800361c:	f1ad fe5e 	bl	0x81b12dc
 8003620:	7ee0      	ldrb	r0, [r4, #27]
 8003622:	3001      	adds	r0, #1
 8003624:	76e0      	strb	r0, [r4, #27]
 8003626:	bc10      	pop	{r4}
 8003628:	bc01      	pop	{r0}
 800362a:	4700      	bx	r0
 800362c:	b3bc      	cbz	r4, 0x800369e
 800362e:	081b      	lsrs	r3, r3, #32
 8003630:	b5f0      	push	{r4, r5, r6, r7, lr}
 8003632:	464f      	mov	r7, r9
 8003634:	4646      	mov	r6, r8
 8003636:	b4c0      	push	{r6, r7}
 8003638:	b083      	sub	sp, #12
 800363a:	1c04      	adds	r4, r0, #0
 800363c:	4688      	mov	r8, r1
 800363e:	980a      	ldr	r0, [sp, #40]	@ 0x28
 8003640:	990b      	ldr	r1, [sp, #44]	@ 0x2c
 8003642:	0612      	lsls	r2, r2, #24
 8003644:	0e15      	lsrs	r5, r2, #24
 8003646:	061b      	lsls	r3, r3, #24
 8003648:	0e1f      	lsrs	r7, r3, #24
 800364a:	0600      	lsls	r0, r0, #24
 800364c:	0e06      	lsrs	r6, r0, #24
 800364e:	0609      	lsls	r1, r1, #24
 8003650:	0e09      	lsrs	r1, r1, #24
 8003652:	4689      	mov	r9, r1
 8003654:	0424      	lsls	r4, r4, #16
 8003656:	0c24      	lsrs	r4, r4, #16
 8003658:	ab02      	add	r3, sp, #8
 800365a:	1c28      	adds	r0, r5, #0
 800365c:	1c21      	adds	r1, r4, #0
 800365e:	aa01      	add	r2, sp, #4
 8003660:	f000 f866 	bl	0x8003730
 8003664:	2d06      	cmp	r5, #6
 8003666:	d832      	bhi.n	0x80036ce
 8003668:	00a8      	lsls	r0, r5, #2
 800366a:	4902      	ldr	r1, [pc, #8]	@ (0x8003674)
 800366c:	1840      	adds	r0, r0, r1
 800366e:	6800      	ldr	r0, [r0, #0]
 8003670:	4687      	mov	pc, r0
 8003672:	0000      	movs	r0, r0
 8003674:	3678      	adds	r6, #120	@ 0x78
 8003676:	0800      	lsrs	r0, r0, #32
 8003678:	3694      	adds	r6, #148	@ 0x94
 800367a:	0800      	lsrs	r0, r0, #32
 800367c:	3694      	adds	r6, #148	@ 0x94
 800367e:	0800      	lsrs	r0, r0, #32
 8003680:	3694      	adds	r6, #148	@ 0x94
 8003682:	0800      	lsrs	r0, r0, #32
 8003684:	36b0      	adds	r6, #176	@ 0xb0
 8003686:	0800      	lsrs	r0, r0, #32
 8003688:	36b0      	adds	r6, #176	@ 0xb0
 800368a:	0800      	lsrs	r0, r0, #32
 800368c:	36b0      	adds	r6, #176	@ 0xb0
 800368e:	0800      	lsrs	r0, r0, #32
 8003690:	3694      	adds	r6, #148	@ 0x94
 8003692:	0800      	lsrs	r0, r0, #32
 8003694:	9801      	ldr	r0, [sp, #4]
 8003696:	4641      	mov	r1, r8
 8003698:	1c3a      	adds	r2, r7, #0
 800369a:	1c33      	adds	r3, r6, #0
 800369c:	f000 f8c8 	bl	0x8003830
 80036a0:	9802      	ldr	r0, [sp, #8]
 80036a2:	4641      	mov	r1, r8
 80036a4:	3120      	adds	r1, #32
 80036a6:	1c3a      	adds	r2, r7, #0
 80036a8:	1c33      	adds	r3, r6, #0
 80036aa:	f000 f8c1 	bl	0x8003830
 80036ae:	e00e      	b.n	0x80036ce
 80036b0:	9801      	ldr	r0, [sp, #4]
 80036b2:	9600      	str	r6, [sp, #0]
 80036b4:	4641      	mov	r1, r8
 80036b6:	1c3a      	adds	r2, r7, #0
 80036b8:	464b      	mov	r3, r9
 80036ba:	f000 f8f1 	bl	0x80038a0
 80036be:	9802      	ldr	r0, [sp, #8]
 80036c0:	4641      	mov	r1, r8
 80036c2:	3120      	adds	r1, #32
 80036c4:	9600      	str	r6, [sp, #0]
 80036c6:	1c3a      	adds	r2, r7, #0
 80036c8:	464b      	mov	r3, r9
 80036ca:	f000 f8e9 	bl	0x80038a0
 80036ce:	b003      	add	sp, #12
 80036d0:	bc18      	pop	{r3, r4}
 80036d2:	4698      	mov	r8, r3
 80036d4:	46a1      	mov	r9, r4
 80036d6:	bcf0      	pop	{r4, r5, r6, r7}
 80036d8:	bc01      	pop	{r0}
 80036da:	4700      	bx	r0
 80036dc:	b570      	push	{r4, r5, r6, lr}
 80036de:	1c06      	adds	r6, r0, #0
 80036e0:	1c0c      	adds	r4, r1, #0
 80036e2:	1c15      	adds	r5, r2, #0
 80036e4:	0424      	lsls	r4, r4, #16
 80036e6:	0c24      	lsrs	r4, r4, #16
 80036e8:	042d      	lsls	r5, r5, #16
 80036ea:	0c2d      	lsrs	r5, r5, #16
 80036ec:	f000 f80c 	bl	0x8003708
 80036f0:	7bf1      	ldrb	r1, [r6, #15]
 80036f2:	0309      	lsls	r1, r1, #12
 80036f4:	430c      	orrs	r4, r1
 80036f6:	8004      	strh	r4, [r0, #0]
 80036f8:	3040      	adds	r0, #64	@ 0x40
 80036fa:	7bf1      	ldrb	r1, [r6, #15]
 80036fc:	0309      	lsls	r1, r1, #12
 80036fe:	430d      	orrs	r5, r1
 8003700:	8005      	strh	r5, [r0, #0]
 8003702:	bc70      	pop	{r4, r5, r6}
 8003704:	bc01      	pop	{r0}
 8003706:	4700      	bx	r0
 8003708:	7ec2      	ldrb	r2, [r0, #27]
 800370a:	7e81      	ldrb	r1, [r0, #26]
 800370c:	1852      	adds	r2, r2, r1
 800370e:	0612      	lsls	r2, r2, #24
 8003710:	0e12      	lsrs	r2, r2, #24
 8003712:	7f41      	ldrb	r1, [r0, #29]
 8003714:	7f03      	ldrb	r3, [r0, #28]
 8003716:	18c9      	adds	r1, r1, r3
 8003718:	0609      	lsls	r1, r1, #24
 800371a:	6800      	ldr	r0, [r0, #0]
 800371c:	0cc9      	lsrs	r1, r1, #19
 800371e:	1889      	adds	r1, r1, r2
 8003720:	0049      	lsls	r1, r1, #1
 8003722:	6900      	ldr	r0, [r0, #16]
 8003724:	1840      	adds	r0, r0, r1
 8003726:	4770      	bx	lr
 8003728:	7bc0      	ldrb	r0, [r0, #15]
 800372a:	0700      	lsls	r0, r0, #28
 800372c:	0c00      	lsrs	r0, r0, #16
 800372e:	4770      	bx	lr
 8003730:	b510      	push	{r4, lr}
 8003732:	1c14      	adds	r4, r2, #0
 8003734:	0600      	lsls	r0, r0, #24
 8003736:	0e00      	lsrs	r0, r0, #24
 8003738:	0409      	lsls	r1, r1, #16
 800373a:	0c0a      	lsrs	r2, r1, #16
 800373c:	2806      	cmp	r0, #6
 800373e:	d86f      	bhi.n	0x8003820
 8003740:	0080      	lsls	r0, r0, #2
 8003742:	4902      	ldr	r1, [pc, #8]	@ (0x800374c)
 8003744:	1840      	adds	r0, r0, r1
 8003746:	6800      	ldr	r0, [r0, #0]
 8003748:	4687      	mov	pc, r0
 800374a:	0000      	movs	r0, r0
 800374c:	3750      	adds	r7, #80	@ 0x50
 800374e:	0800      	lsrs	r0, r0, #32
 8003750:	376c      	adds	r7, #108	@ 0x6c
 8003752:	0800      	lsrs	r0, r0, #32
 8003754:	377c      	adds	r7, #124	@ 0x7c
 8003756:	0800      	lsrs	r0, r0, #32
 8003758:	3794      	adds	r7, #148	@ 0x94
 800375a:	0800      	lsrs	r0, r0, #32
 800375c:	37ac      	adds	r7, #172	@ 0xac
 800375e:	0800      	lsrs	r0, r0, #32
 8003760:	37d0      	adds	r7, #208	@ 0xd0
 8003762:	0800      	lsrs	r0, r0, #32
 8003764:	37f0      	adds	r7, #240	@ 0xf0
 8003766:	0800      	lsrs	r0, r0, #32
 8003768:	3808      	subs	r0, #8
 800376a:	0800      	lsrs	r0, r0, #32
 800376c:	0110      	lsls	r0, r2, #4
 800376e:	4902      	ldr	r1, [pc, #8]	@ (0x8003778)
 8003770:	1840      	adds	r0, r0, r1
 8003772:	6020      	str	r0, [r4, #0]
 8003774:	3008      	adds	r0, #8
 8003776:	e052      	b.n	0x800381e
 8003778:	3aac      	subs	r2, #172	@ 0xac
 800377a:	081b      	lsrs	r3, r3, #32
 800377c:	4803      	ldr	r0, [pc, #12]	@ (0x800378c)
 800377e:	0091      	lsls	r1, r2, #2
 8003780:	1809      	adds	r1, r1, r0
 8003782:	7808      	ldrb	r0, [r1, #0]
 8003784:	00c0      	lsls	r0, r0, #3
 8003786:	4a02      	ldr	r2, [pc, #8]	@ (0x8003790)
 8003788:	e044      	b.n	0x8003814
 800378a:	0000      	movs	r0, r0
 800378c:	34a8      	adds	r4, #168	@ 0xa8
 800378e:	081b      	lsrs	r3, r3, #32
 8003790:	49ac      	ldr	r1, [pc, #688]	@ (0x8003a44)
 8003792:	081b      	lsrs	r3, r3, #32
 8003794:	4903      	ldr	r1, [pc, #12]	@ (0x80037a4)
 8003796:	6021      	str	r1, [r4, #0]
 8003798:	00d0      	lsls	r0, r2, #3
 800379a:	4a03      	ldr	r2, [pc, #12]	@ (0x80037a8)
 800379c:	1889      	adds	r1, r1, r2
 800379e:	1840      	adds	r0, r0, r1
 80037a0:	e03d      	b.n	0x800381e
 80037a2:	0000      	movs	r0, r0
 80037a4:	504c      	str	r4, [r1, r1]
 80037a6:	081b      	lsrs	r3, r3, #32
 80037a8:	f960 ffff 			@ <UNDEFINED> instruction: 0xf960ffff
 80037ac:	4806      	ldr	r0, [pc, #24]	@ (0x80037c8)
 80037ae:	4010      	ands	r0, r2
 80037b0:	0180      	lsls	r0, r0, #6
 80037b2:	210f      	movs	r1, #15
 80037b4:	4011      	ands	r1, r2
 80037b6:	0149      	lsls	r1, r1, #5
 80037b8:	1840      	adds	r0, r0, r1
 80037ba:	4904      	ldr	r1, [pc, #16]	@ (0x80037cc)
 80037bc:	1840      	adds	r0, r0, r1
 80037be:	6020      	str	r0, [r4, #0]
 80037c0:	2180      	movs	r1, #128	@ 0x80
 80037c2:	0089      	lsls	r1, r1, #2
 80037c4:	1840      	adds	r0, r0, r1
 80037c6:	e02a      	b.n	0x800381e
 80037c8:	fff0 0000 	vrev64.8	d16, d0
 80037cc:	6d2c      	ldr	r4, [r5, #80]	@ 0x50
 80037ce:	081b      	lsrs	r3, r3, #32
 80037d0:	4805      	ldr	r0, [pc, #20]	@ (0x80037e8)
 80037d2:	0091      	lsls	r1, r2, #2
 80037d4:	1809      	adds	r1, r1, r0
 80037d6:	7808      	ldrb	r0, [r1, #0]
 80037d8:	0140      	lsls	r0, r0, #5
 80037da:	4a04      	ldr	r2, [pc, #16]	@ (0x80037ec)
 80037dc:	1880      	adds	r0, r0, r2
 80037de:	6020      	str	r0, [r4, #0]
 80037e0:	7848      	ldrb	r0, [r1, #1]
 80037e2:	0140      	lsls	r0, r0, #5
 80037e4:	e01a      	b.n	0x800381c
 80037e6:	0000      	movs	r0, r0
 80037e8:	34a8      	adds	r4, #168	@ 0xa8
 80037ea:	081b      	lsrs	r3, r3, #32
 80037ec:	51ac      	str	r4, [r5, r6]
 80037ee:	081b      	lsrs	r3, r3, #32
 80037f0:	4903      	ldr	r1, [pc, #12]	@ (0x8003800)
 80037f2:	6021      	str	r1, [r4, #0]
 80037f4:	0150      	lsls	r0, r2, #5
 80037f6:	4a03      	ldr	r2, [pc, #12]	@ (0x8003804)
 80037f8:	1889      	adds	r1, r1, r2
 80037fa:	1840      	adds	r0, r0, r1
 80037fc:	e00f      	b.n	0x800381e
 80037fe:	0000      	movs	r0, r0
 8003800:	6c2c      	ldr	r4, [r5, #64]	@ 0x40
 8003802:	081b      	lsrs	r3, r3, #32
 8003804:	e580      	b.n	0x8003308
 8003806:	ffff 4807 	vtbl.8	d20, {d15}, d7
 800380a:	0091      	lsls	r1, r2, #2
 800380c:	1809      	adds	r1, r1, r0
 800380e:	7808      	ldrb	r0, [r1, #0]
 8003810:	00c0      	lsls	r0, r0, #3
 8003812:	4a06      	ldr	r2, [pc, #24]	@ (0x800382c)
 8003814:	1880      	adds	r0, r0, r2
 8003816:	6020      	str	r0, [r4, #0]
 8003818:	7848      	ldrb	r0, [r1, #1]
 800381a:	00c0      	lsls	r0, r0, #3
 800381c:	1880      	adds	r0, r0, r2
 800381e:	6018      	str	r0, [r3, #0]
 8003820:	bc10      	pop	{r4}
 8003822:	bc01      	pop	{r0}
 8003824:	4700      	bx	r0
 8003826:	0000      	movs	r0, r0
 8003828:	3884      	subs	r0, #132	@ 0x84
 800382a:	081b      	lsrs	r3, r3, #32
 800382c:	acac      	add	r4, sp, #688	@ 0x2b0
 800382e:	081b      	lsrs	r3, r3, #32
 8003830:	b5f0      	push	{r4, r5, r6, r7, lr}
 8003832:	4657      	mov	r7, sl
 8003834:	464e      	mov	r6, r9
 8003836:	4645      	mov	r5, r8
 8003838:	b4e0      	push	{r5, r6, r7}
 800383a:	4682      	mov	sl, r0
 800383c:	4689      	mov	r9, r1
 800383e:	0612      	lsls	r2, r2, #24
 8003840:	0e12      	lsrs	r2, r2, #24
 8003842:	4694      	mov	ip, r2
 8003844:	061b      	lsls	r3, r3, #24
 8003846:	0e1f      	lsrs	r7, r3, #24
 8003848:	2100      	movs	r1, #0
 800384a:	2080      	movs	r0, #128	@ 0x80
 800384c:	4680      	mov	r8, r0
 800384e:	2400      	movs	r4, #0
 8003850:	4652      	mov	r2, sl
 8003852:	1850      	adds	r0, r2, r1
 8003854:	7803      	ldrb	r3, [r0, #0]
 8003856:	2200      	movs	r2, #0
 8003858:	008d      	lsls	r5, r1, #2
 800385a:	1c4e      	adds	r6, r1, #1
 800385c:	1c18      	adds	r0, r3, #0
 800385e:	4641      	mov	r1, r8
 8003860:	4008      	ands	r0, r1
 8003862:	2800      	cmp	r0, #0
 8003864:	d002      	beq.n	0x800386c
 8003866:	0091      	lsls	r1, r2, #2
 8003868:	4660      	mov	r0, ip
 800386a:	e001      	b.n	0x8003870
 800386c:	0091      	lsls	r1, r2, #2
 800386e:	1c38      	adds	r0, r7, #0
 8003870:	4088      	lsls	r0, r1
 8003872:	4304      	orrs	r4, r0
 8003874:	0658      	lsls	r0, r3, #25
 8003876:	0e03      	lsrs	r3, r0, #24
 8003878:	1c50      	adds	r0, r2, #1
 800387a:	0600      	lsls	r0, r0, #24
 800387c:	0e02      	lsrs	r2, r0, #24
 800387e:	2a07      	cmp	r2, #7
 8003880:	d9ec      	bls.n	0x800385c
 8003882:	464a      	mov	r2, r9
 8003884:	18a8      	adds	r0, r5, r2
 8003886:	6004      	str	r4, [r0, #0]
 8003888:	0630      	lsls	r0, r6, #24
 800388a:	0e01      	lsrs	r1, r0, #24
 800388c:	2907      	cmp	r1, #7
 800388e:	d9de      	bls.n	0x800384e
 8003890:	bc38      	pop	{r3, r4, r5}
 8003892:	4698      	mov	r8, r3
 8003894:	46a1      	mov	r9, r4
 8003896:	46aa      	mov	sl, r5
 8003898:	bcf0      	pop	{r4, r5, r6, r7}
 800389a:	bc01      	pop	{r0}
 800389c:	4700      	bx	r0
 800389e:	0000      	movs	r0, r0
 80038a0:	b5f0      	push	{r4, r5, r6, r7, lr}
 80038a2:	464f      	mov	r7, r9
 80038a4:	4646      	mov	r6, r8
 80038a6:	b4c0      	push	{r6, r7}
 80038a8:	4689      	mov	r9, r1
 80038aa:	9907      	ldr	r1, [sp, #28]
 80038ac:	0612      	lsls	r2, r2, #24
 80038ae:	0e17      	lsrs	r7, r2, #24
 80038b0:	061b      	lsls	r3, r3, #24
 80038b2:	0e1e      	lsrs	r6, r3, #24
 80038b4:	0609      	lsls	r1, r1, #24
 80038b6:	0e0d      	lsrs	r5, r1, #24
 80038b8:	2400      	movs	r4, #0
 80038ba:	4906      	ldr	r1, [pc, #24]	@ (0x80038d4)
 80038bc:	4688      	mov	r8, r1
 80038be:	21f0      	movs	r1, #240	@ 0xf0
 80038c0:	468c      	mov	ip, r1
 80038c2:	1c03      	adds	r3, r0, #0
 80038c4:	7818      	ldrb	r0, [r3, #0]
 80038c6:	4661      	mov	r1, ip
 80038c8:	4001      	ands	r1, r0
 80038ca:	2900      	cmp	r1, #0
 80038cc:	d104      	bne.n	0x80038d8
 80038ce:	0728      	lsls	r0, r5, #28
 80038d0:	0e02      	lsrs	r2, r0, #24
 80038d2:	e00d      	b.n	0x80038f0
 80038d4:	0330      	lsls	r0, r6, #12
 80038d6:	0300      	lsls	r0, r0, #12
 80038d8:	29f0      	cmp	r1, #240	@ 0xf0
 80038da:	d102      	bne.n	0x80038e2
 80038dc:	0738      	lsls	r0, r7, #28
 80038de:	0e02      	lsrs	r2, r0, #24
 80038e0:	e006      	b.n	0x80038f0
 80038e2:	29e0      	cmp	r1, #224	@ 0xe0
 80038e4:	d102      	bne.n	0x80038ec
 80038e6:	0730      	lsls	r0, r6, #28
 80038e8:	0e02      	lsrs	r2, r0, #24
 80038ea:	e001      	b.n	0x80038f0
 80038ec:	4662      	mov	r2, ip
 80038ee:	400a      	ands	r2, r1
 80038f0:	7818      	ldrb	r0, [r3, #0]
 80038f2:	210f      	movs	r1, #15
 80038f4:	4001      	ands	r1, r0
 80038f6:	2900      	cmp	r1, #0
 80038f8:	d101      	bne.n	0x80038fe
 80038fa:	432a      	orrs	r2, r5
 80038fc:	e008      	b.n	0x8003910
 80038fe:	290f      	cmp	r1, #15
 8003900:	d101      	bne.n	0x8003906
 8003902:	433a      	orrs	r2, r7
 8003904:	e004      	b.n	0x8003910
 8003906:	290e      	cmp	r1, #14
 8003908:	d101      	bne.n	0x800390e
 800390a:	4332      	orrs	r2, r6
 800390c:	e000      	b.n	0x8003910
 800390e:	430a      	orrs	r2, r1
 8003910:	4641      	mov	r1, r8
 8003912:	1860      	adds	r0, r4, r1
 8003914:	7002      	strb	r2, [r0, #0]
 8003916:	3301      	adds	r3, #1
 8003918:	3401      	adds	r4, #1
 800391a:	2c1f      	cmp	r4, #31
 800391c:	ddd2      	ble.n	0x80038c4
 800391e:	4a05      	ldr	r2, [pc, #20]	@ (0x8003934)
 8003920:	4640      	mov	r0, r8
 8003922:	4649      	mov	r1, r9
 8003924:	f1ad fcb6 	bl	0x81b1294
 8003928:	bc18      	pop	{r3, r4}
 800392a:	4698      	mov	r8, r3
 800392c:	46a1      	mov	r9, r4
 800392e:	bcf0      	pop	{r4, r5, r6, r7}
 8003930:	bc01      	pop	{r0}
 8003932:	4700      	bx	r0
 8003934:	0008      	movs	r0, r1
 8003936:	0400      	lsls	r0, r0, #16
 8003938:	b500      	push	{lr}
 800393a:	f000 f813 	bl	0x8003964
 800393e:	0600      	lsls	r0, r0, #24
 8003940:	2800      	cmp	r0, #0
 8003942:	d10b      	bne.n	0x800395c
 8003944:	4903      	ldr	r1, [pc, #12]	@ (0x8003954)
 8003946:	4804      	ldr	r0, [pc, #16]	@ (0x8003958)
 8003948:	7d00      	ldrb	r0, [r0, #20]
 800394a:	0740      	lsls	r0, r0, #29
 800394c:	0f40      	lsrs	r0, r0, #29
 800394e:	1840      	adds	r0, r0, r1
 8003950:	7800      	ldrb	r0, [r0, #0]
 8003952:	e004      	b.n	0x800395e
 8003954:	b3d8      	cbz	r0, 0x80039ce
 8003956:	081b      	lsrs	r3, r3, #32
 8003958:	4c04      	ldr	r4, [pc, #16]	@ (0x800396c)
 800395a:	0202      	lsls	r2, r0, #8
 800395c:	2004      	movs	r0, #4
 800395e:	bc02      	pop	{r1}
 8003960:	4708      	bx	r1
 8003962:	0000      	movs	r0, r0
 8003964:	b500      	push	{lr}
 8003966:	4806      	ldr	r0, [pc, #24]	@ (0x8003980)
 8003968:	7800      	ldrb	r0, [r0, #0]
 800396a:	2802      	cmp	r0, #2
 800396c:	d014      	beq.n	0x8003998
 800396e:	2800      	cmp	r0, #0
 8003970:	d016      	beq.n	0x80039a0
 8003972:	2803      	cmp	r0, #3
 8003974:	d108      	bne.n	0x8003988
 8003976:	4803      	ldr	r0, [pc, #12]	@ (0x8003984)
 8003978:	7800      	ldrb	r0, [r0, #0]
 800397a:	2800      	cmp	r0, #0
 800397c:	d10c      	bne.n	0x8003998
 800397e:	e00f      	b.n	0x80039a0
 8003980:	0324      	lsls	r4, r4, #12
 8003982:	0300      	lsls	r0, r0, #12
 8003984:	8396      	strh	r6, [r2, #28]
 8003986:	0203      	lsls	r3, r0, #8
 8003988:	2801      	cmp	r0, #1
 800398a:	d109      	bne.n	0x80039a0
 800398c:	4803      	ldr	r0, [pc, #12]	@ (0x800399c)
 800398e:	8801      	ldrh	r1, [r0, #0]
 8003990:	2002      	movs	r0, #2
 8003992:	4008      	ands	r0, r1
 8003994:	2800      	cmp	r0, #0
 8003996:	d003      	beq.n	0x80039a0
 8003998:	2001      	movs	r0, #1
 800399a:	e002      	b.n	0x80039a2
 800399c:	3758      	adds	r7, #88	@ 0x58
 800399e:	0202      	lsls	r2, r0, #8
 80039a0:	2000      	movs	r0, #0
 80039a2:	bc02      	pop	{r1}
 80039a4:	4708      	bx	r1
 80039a6:	0000      	movs	r0, r0
 80039a8:	b500      	push	{lr}
 80039aa:	7a81      	ldrb	r1, [r0, #10]
 80039ac:	2901      	cmp	r1, #1
 80039ae:	d00c      	beq.n	0x80039ca
 80039b0:	2901      	cmp	r1, #1
 80039b2:	dc02      	bgt.n	0x80039ba
 80039b4:	2900      	cmp	r1, #0
 80039b6:	d005      	beq.n	0x80039c4
 80039b8:	e00c      	b.n	0x80039d4
 80039ba:	2902      	cmp	r1, #2
 80039bc:	d00a      	beq.n	0x80039d4
 80039be:	2903      	cmp	r1, #3
 80039c0:	d006      	beq.n	0x80039d0
 80039c2:	e007      	b.n	0x80039d4
 80039c4:	f000 f808 	bl	0x80039d8
 80039c8:	e004      	b.n	0x80039d4
 80039ca:	f000 f839 	bl	0x8003a40
 80039ce:	e001      	b.n	0x80039d4
 80039d0:	f000 f850 	bl	0x8003a74
 80039d4:	bc01      	pop	{r0}
 80039d6:	4700      	bx	r0
 80039d8:	b510      	push	{r4, lr}
 80039da:	1c02      	adds	r2, r0, #0
 80039dc:	7f53      	ldrb	r3, [r2, #29]
 80039de:	2b00      	cmp	r3, #0
 80039e0:	d10c      	bne.n	0x80039fc
 80039e2:	4805      	ldr	r0, [pc, #20]	@ (0x80039f8)
 80039e4:	7800      	ldrb	r0, [r0, #0]
 80039e6:	0040      	lsls	r0, r0, #1
 80039e8:	3004      	adds	r0, #4
 80039ea:	2100      	movs	r1, #0
 80039ec:	8310      	strh	r0, [r2, #24]
 80039ee:	76d1      	strb	r1, [r2, #27]
 80039f0:	1c98      	adds	r0, r3, #2
 80039f2:	7750      	strb	r0, [r2, #29]
 80039f4:	e01e      	b.n	0x8003a34
 80039f6:	0000      	movs	r0, r0
 80039f8:	0325      	lsls	r5, r4, #12
 80039fa:	0300      	lsls	r0, r0, #12
 80039fc:	7a11      	ldrb	r1, [r2, #8]
 80039fe:	2002      	movs	r0, #2
 8003a00:	4008      	ands	r0, r1
 8003a02:	1c0b      	adds	r3, r1, #0
 8003a04:	2800      	cmp	r0, #0
 8003a06:	d009      	beq.n	0x8003a1c
 8003a08:	4903      	ldr	r1, [pc, #12]	@ (0x8003a18)
 8003a0a:	7808      	ldrb	r0, [r1, #0]
 8003a0c:	0040      	lsls	r0, r0, #1
 8003a0e:	3004      	adds	r0, #4
 8003a10:	8310      	strh	r0, [r2, #24]
 8003a12:	1c0c      	adds	r4, r1, #0
 8003a14:	e005      	b.n	0x8003a22
 8003a16:	0000      	movs	r0, r0
 8003a18:	0325      	lsls	r5, r4, #12
 8003a1a:	0300      	lsls	r0, r0, #12
 8003a1c:	2004      	movs	r0, #4
 8003a1e:	8310      	strh	r0, [r2, #24]
 8003a20:	4c06      	ldr	r4, [pc, #24]	@ (0x8003a3c)
 8003a22:	2002      	movs	r0, #2
 8003a24:	4058      	eors	r0, r3
 8003a26:	2100      	movs	r1, #0
 8003a28:	7210      	strb	r0, [r2, #8]
 8003a2a:	76d1      	strb	r1, [r2, #27]
 8003a2c:	7821      	ldrb	r1, [r4, #0]
 8003a2e:	1c10      	adds	r0, r2, #0
 8003a30:	f000 f83a 	bl	0x8003aa8
 8003a34:	bc10      	pop	{r4}
 8003a36:	bc01      	pop	{r0}
 8003a38:	4700      	bx	r0
 8003a3a:	0000      	movs	r0, r0
 8003a3c:	0325      	lsls	r5, r4, #12
 8003a3e:	0300      	lsls	r0, r0, #12
 8003a40:	b500      	push	{lr}
 8003a42:	1c02      	adds	r2, r0, #0
 8003a44:	7f50      	ldrb	r0, [r2, #29]
 8003a46:	1c01      	adds	r1, r0, #0
 8003a48:	2900      	cmp	r1, #0
 8003a4a:	d103      	bne.n	0x8003a54
 8003a4c:	76d1      	strb	r1, [r2, #27]
 8003a4e:	3002      	adds	r0, #2
 8003a50:	7750      	strb	r0, [r2, #29]
 8003a52:	e00a      	b.n	0x8003a6a
 8003a54:	7a10      	ldrb	r0, [r2, #8]
 8003a56:	2102      	movs	r1, #2
 8003a58:	4048      	eors	r0, r1
 8003a5a:	2100      	movs	r1, #0
 8003a5c:	7210      	strb	r0, [r2, #8]
 8003a5e:	76d1      	strb	r1, [r2, #27]
 8003a60:	4803      	ldr	r0, [pc, #12]	@ (0x8003a70)
 8003a62:	7801      	ldrb	r1, [r0, #0]
 8003a64:	1c10      	adds	r0, r2, #0
 8003a66:	f000 f81f 	bl	0x8003aa8
 8003a6a:	bc01      	pop	{r0}
 8003a6c:	4700      	bx	r0
 8003a6e:	0000      	movs	r0, r0
 8003a70:	0325      	lsls	r5, r4, #12
 8003a72:	0300      	lsls	r0, r0, #12
 8003a74:	b500      	push	{lr}
 8003a76:	1c02      	adds	r2, r0, #0
 8003a78:	7f50      	ldrb	r0, [r2, #29]
 8003a7a:	1c01      	adds	r1, r0, #0
 8003a7c:	2900      	cmp	r1, #0
 8003a7e:	d103      	bne.n	0x8003a88
 8003a80:	76d1      	strb	r1, [r2, #27]
 8003a82:	3002      	adds	r0, #2
 8003a84:	7750      	strb	r0, [r2, #29]
 8003a86:	e00a      	b.n	0x8003a9e
 8003a88:	7a10      	ldrb	r0, [r2, #8]
 8003a8a:	2102      	movs	r1, #2
 8003a8c:	4048      	eors	r0, r1
 8003a8e:	2100      	movs	r1, #0
 8003a90:	7210      	strb	r0, [r2, #8]
 8003a92:	76d1      	strb	r1, [r2, #27]
 8003a94:	4803      	ldr	r0, [pc, #12]	@ (0x8003aa4)
 8003a96:	7801      	ldrb	r1, [r0, #0]
 8003a98:	1c10      	adds	r0, r2, #0
 8003a9a:	f000 f839 	bl	0x8003b10
 8003a9e:	bc01      	pop	{r0}
 8003aa0:	4700      	bx	r0
 8003aa2:	0000      	movs	r0, r0
 8003aa4:	0325      	lsls	r5, r4, #12
 8003aa6:	0300      	lsls	r0, r0, #12
 8003aa8:	b5f0      	push	{r4, r5, r6, r7, lr}
 8003aaa:	4647      	mov	r7, r8
 8003aac:	b480      	push	{r7}
 8003aae:	1c05      	adds	r5, r0, #0
 8003ab0:	0409      	lsls	r1, r1, #16
 8003ab2:	0c0f      	lsrs	r7, r1, #16
 8003ab4:	f7ff fe38 	bl	0x8003728
 8003ab8:	1c04      	adds	r4, r0, #0
 8003aba:	1c28      	adds	r0, r5, #0
 8003abc:	f000 fb7e 	bl	0x80041bc
 8003ac0:	4304      	orrs	r4, r0
 8003ac2:	0424      	lsls	r4, r4, #16
 8003ac4:	0c26      	lsrs	r6, r4, #16
 8003ac6:	1c28      	adds	r0, r5, #0
 8003ac8:	f7ff fe1e 	bl	0x8003708
 8003acc:	1c04      	adds	r4, r0, #0
 8003ace:	3c80      	subs	r4, #128	@ 0x80
 8003ad0:	2080      	movs	r0, #128	@ 0x80
 8003ad2:	1900      	adds	r0, r0, r4
 8003ad4:	4680      	mov	r8, r0
 8003ad6:	1c21      	adds	r1, r4, #0
 8003ad8:	1c3a      	adds	r2, r7, #0
 8003ada:	f1ad fbdb 	bl	0x81b1294
 8003ade:	1c25      	adds	r5, r4, #0
 8003ae0:	35c0      	adds	r5, #192	@ 0xc0
 8003ae2:	3440      	adds	r4, #64	@ 0x40
 8003ae4:	1c28      	adds	r0, r5, #0
 8003ae6:	1c21      	adds	r1, r4, #0
 8003ae8:	1c3a      	adds	r2, r7, #0
 8003aea:	f1ad fbd3 	bl	0x81b1294
 8003aee:	2f00      	cmp	r7, #0
 8003af0:	d009      	beq.n	0x8003b06
 8003af2:	1c2c      	adds	r4, r5, #0
 8003af4:	4640      	mov	r0, r8
 8003af6:	1c3a      	adds	r2, r7, #0
 8003af8:	8006      	strh	r6, [r0, #0]
 8003afa:	8026      	strh	r6, [r4, #0]
 8003afc:	3402      	adds	r4, #2
 8003afe:	3002      	adds	r0, #2
 8003b00:	3a01      	subs	r2, #1
 8003b02:	2a00      	cmp	r2, #0
 8003b04:	d1f8      	bne.n	0x8003af8
 8003b06:	bc08      	pop	{r3}
 8003b08:	4698      	mov	r8, r3
 8003b0a:	bcf0      	pop	{r4, r5, r6, r7}
 8003b0c:	bc01      	pop	{r0}
 8003b0e:	4700      	bx	r0
 8003b10:	b570      	push	{r4, r5, r6, lr}
 8003b12:	4656      	mov	r6, sl
 8003b14:	464d      	mov	r5, r9
 8003b16:	4644      	mov	r4, r8
 8003b18:	b470      	push	{r4, r5, r6}
 8003b1a:	1c05      	adds	r5, r0, #0
 8003b1c:	060c      	lsls	r4, r1, #24
 8003b1e:	0e24      	lsrs	r4, r4, #24
 8003b20:	f7ff fcde 	bl	0x80034e0
 8003b24:	1c02      	adds	r2, r0, #0
 8003b26:	481d      	ldr	r0, [pc, #116]	@ (0x8003b9c)
 8003b28:	1811      	adds	r1, r2, r0
 8003b2a:	4b1d      	ldr	r3, [pc, #116]	@ (0x8003ba0)
 8003b2c:	469a      	mov	sl, r3
 8003b2e:	00e0      	lsls	r0, r4, #3
 8003b30:	2380      	movs	r3, #128	@ 0x80
 8003b32:	04db      	lsls	r3, r3, #19
 8003b34:	4699      	mov	r9, r3
 8003b36:	4318      	orrs	r0, r3
 8003b38:	4680      	mov	r8, r0
 8003b3a:	1c10      	adds	r0, r2, #0
 8003b3c:	4642      	mov	r2, r8
 8003b3e:	f1ad fba9 	bl	0x81b1294
 8003b42:	1c28      	adds	r0, r5, #0
 8003b44:	f7ff fccc 	bl	0x80034e0
 8003b48:	26f0      	movs	r6, #240	@ 0xf0
 8003b4a:	00b6      	lsls	r6, r6, #2
 8003b4c:	1982      	adds	r2, r0, r6
 8003b4e:	4b15      	ldr	r3, [pc, #84]	@ (0x8003ba4)
 8003b50:	18c1      	adds	r1, r0, r3
 8003b52:	1c10      	adds	r0, r2, #0
 8003b54:	4642      	mov	r2, r8
 8003b56:	f1ad fb9d 	bl	0x81b1294
 8003b5a:	1c28      	adds	r0, r5, #0
 8003b5c:	2100      	movs	r1, #0
 8003b5e:	f7ff fc81 	bl	0x8003464
 8003b62:	1c28      	adds	r0, r5, #0
 8003b64:	f7ff fcbc 	bl	0x80034e0
 8003b68:	1c05      	adds	r5, r0, #0
 8003b6a:	1c29      	adds	r1, r5, #0
 8003b6c:	3120      	adds	r1, #32
 8003b6e:	3c01      	subs	r4, #1
 8003b70:	00e4      	lsls	r4, r4, #3
 8003b72:	4650      	mov	r0, sl
 8003b74:	4004      	ands	r4, r0
 8003b76:	464b      	mov	r3, r9
 8003b78:	431c      	orrs	r4, r3
 8003b7a:	1c28      	adds	r0, r5, #0
 8003b7c:	1c22      	adds	r2, r4, #0
 8003b7e:	f1ad fb89 	bl	0x81b1294
 8003b82:	19ae      	adds	r6, r5, r6
 8003b84:	1c28      	adds	r0, r5, #0
 8003b86:	1c31      	adds	r1, r6, #0
 8003b88:	4642      	mov	r2, r8
 8003b8a:	f1ad fb83 	bl	0x81b1294
 8003b8e:	bc38      	pop	{r3, r4, r5}
 8003b90:	4698      	mov	r8, r3
 8003b92:	46a1      	mov	r9, r4
 8003b94:	46aa      	mov	sl, r5
 8003b96:	bc70      	pop	{r4, r5, r6}
 8003b98:	bc01      	pop	{r0}
 8003b9a:	4700      	bx	r0
 8003b9c:	f880 ffff 	strb.w	pc, [r0, #4095]	@ 0xfff
 8003ba0:	ffff 001f 	vshr.u32	d16, d15, #1
 8003ba4:	fc40 ffff 			@ <UNDEFINED> instruction: 0xfc40ffff
 8003ba8:	b510      	push	{r4, lr}
 8003baa:	1c04      	adds	r4, r0, #0
 8003bac:	7aa0      	ldrb	r0, [r4, #10]
 8003bae:	2801      	cmp	r0, #1
 8003bb0:	d014      	beq.n	0x8003bdc
 8003bb2:	2801      	cmp	r0, #1
 8003bb4:	dc02      	bgt.n	0x8003bbc
 8003bb6:	2800      	cmp	r0, #0
 8003bb8:	d005      	beq.n	0x8003bc6
 8003bba:	e01c      	b.n	0x8003bf6
 8003bbc:	2802      	cmp	r0, #2
 8003bbe:	d01a      	beq.n	0x8003bf6
 8003bc0:	2803      	cmp	r0, #3
 8003bc2:	d013      	beq.n	0x8003bec
 8003bc4:	e017      	b.n	0x8003bf6
 8003bc6:	4804      	ldr	r0, [pc, #16]	@ (0x8003bd8)
 8003bc8:	7801      	ldrb	r1, [r0, #0]
 8003bca:	1c20      	adds	r0, r4, #0
 8003bcc:	f000 f818 	bl	0x8003c00
 8003bd0:	2004      	movs	r0, #4
 8003bd2:	8320      	strh	r0, [r4, #24]
 8003bd4:	e00f      	b.n	0x8003bf6
 8003bd6:	0000      	movs	r0, r0
 8003bd8:	0325      	lsls	r5, r4, #12
 8003bda:	0300      	lsls	r0, r0, #12
 8003bdc:	4802      	ldr	r0, [pc, #8]	@ (0x8003be8)
 8003bde:	7801      	ldrb	r1, [r0, #0]
 8003be0:	1c20      	adds	r0, r4, #0
 8003be2:	f000 f80d 	bl	0x8003c00
 8003be6:	e006      	b.n	0x8003bf6
 8003be8:	0325      	lsls	r5, r4, #12
 8003bea:	0300      	lsls	r0, r0, #12
 8003bec:	4803      	ldr	r0, [pc, #12]	@ (0x8003bfc)
 8003bee:	7801      	ldrb	r1, [r0, #0]
 8003bf0:	1c20      	adds	r0, r4, #0
 8003bf2:	f000 f831 	bl	0x8003c58
 8003bf6:	bc10      	pop	{r4}
 8003bf8:	bc01      	pop	{r0}
 8003bfa:	4700      	bx	r0
 8003bfc:	0325      	lsls	r5, r4, #12
 8003bfe:	0300      	lsls	r0, r0, #12
 8003c00:	b5f0      	push	{r4, r5, r6, r7, lr}
 8003c02:	1c05      	adds	r5, r0, #0
 8003c04:	0609      	lsls	r1, r1, #24
 8003c06:	0e0e      	lsrs	r6, r1, #24
 8003c08:	2000      	movs	r0, #0
 8003c0a:	76e8      	strb	r0, [r5, #27]
 8003c0c:	7768      	strb	r0, [r5, #29]
 8003c0e:	7228      	strb	r0, [r5, #8]
 8003c10:	1c28      	adds	r0, r5, #0
 8003c12:	f7ff fd79 	bl	0x8003708
 8003c16:	1c07      	adds	r7, r0, #0
 8003c18:	1c28      	adds	r0, r5, #0
 8003c1a:	f7ff fd85 	bl	0x8003728
 8003c1e:	1c04      	adds	r4, r0, #0
 8003c20:	1c28      	adds	r0, r5, #0
 8003c22:	f000 facb 	bl	0x80041bc
 8003c26:	4304      	orrs	r4, r0
 8003c28:	0424      	lsls	r4, r4, #16
 8003c2a:	0c24      	lsrs	r4, r4, #16
 8003c2c:	2000      	movs	r0, #0
 8003c2e:	2100      	movs	r1, #0
 8003c30:	1c43      	adds	r3, r0, #1
 8003c32:	42b1      	cmp	r1, r6
 8003c34:	d209      	bcs.n	0x8003c4a
 8003c36:	0142      	lsls	r2, r0, #5
 8003c38:	1850      	adds	r0, r2, r1
 8003c3a:	0040      	lsls	r0, r0, #1
 8003c3c:	19c0      	adds	r0, r0, r7
 8003c3e:	8004      	strh	r4, [r0, #0]
 8003c40:	1c48      	adds	r0, r1, #1
 8003c42:	0600      	lsls	r0, r0, #24
 8003c44:	0e01      	lsrs	r1, r0, #24
 8003c46:	42b1      	cmp	r1, r6
 8003c48:	d3f6      	bcc.n	0x8003c38
 8003c4a:	0618      	lsls	r0, r3, #24
 8003c4c:	0e00      	lsrs	r0, r0, #24
 8003c4e:	2803      	cmp	r0, #3
 8003c50:	d9ed      	bls.n	0x8003c2e
 8003c52:	bcf0      	pop	{r4, r5, r6, r7}
 8003c54:	bc01      	pop	{r0}
 8003c56:	4700      	bx	r0
 8003c58:	b570      	push	{r4, r5, r6, lr}
 8003c5a:	4656      	mov	r6, sl
 8003c5c:	464d      	mov	r5, r9
 8003c5e:	4644      	mov	r4, r8
 8003c60:	b470      	push	{r4, r5, r6}
 8003c62:	b081      	sub	sp, #4
 8003c64:	4680      	mov	r8, r0
 8003c66:	060e      	lsls	r6, r1, #24
 8003c68:	0e36      	lsrs	r6, r6, #24
 8003c6a:	2000      	movs	r0, #0
 8003c6c:	4641      	mov	r1, r8
 8003c6e:	76c8      	strb	r0, [r1, #27]
 8003c70:	7748      	strb	r0, [r1, #29]
 8003c72:	7208      	strb	r0, [r1, #8]
 8003c74:	4640      	mov	r0, r8
 8003c76:	2100      	movs	r1, #0
 8003c78:	f7ff fbf4 	bl	0x8003464
 8003c7c:	4640      	mov	r0, r8
 8003c7e:	f7ff fc2f 	bl	0x80034e0
 8003c82:	1c05      	adds	r5, r0, #0
 8003c84:	1c29      	adds	r1, r5, #0
 8003c86:	3120      	adds	r1, #32
 8003c88:	1e72      	subs	r2, r6, #1
 8003c8a:	00d2      	lsls	r2, r2, #3
 8003c8c:	481c      	ldr	r0, [pc, #112]	@ (0x8003d00)
 8003c8e:	4682      	mov	sl, r0
 8003c90:	4002      	ands	r2, r0
 8003c92:	2080      	movs	r0, #128	@ 0x80
 8003c94:	04c0      	lsls	r0, r0, #19
 8003c96:	4681      	mov	r9, r0
 8003c98:	4302      	orrs	r2, r0
 8003c9a:	1c28      	adds	r0, r5, #0
 8003c9c:	f1ad fafa 	bl	0x81b1294
 8003ca0:	20f0      	movs	r0, #240	@ 0xf0
 8003ca2:	0080      	lsls	r0, r0, #2
 8003ca4:	1829      	adds	r1, r5, r0
 8003ca6:	00f4      	lsls	r4, r6, #3
 8003ca8:	4650      	mov	r0, sl
 8003caa:	4004      	ands	r4, r0
 8003cac:	4648      	mov	r0, r9
 8003cae:	4304      	orrs	r4, r0
 8003cb0:	1c28      	adds	r0, r5, #0
 8003cb2:	1c22      	adds	r2, r4, #0
 8003cb4:	f1ad faee 	bl	0x81b1294
 8003cb8:	20f0      	movs	r0, #240	@ 0xf0
 8003cba:	00c0      	lsls	r0, r0, #3
 8003cbc:	1829      	adds	r1, r5, r0
 8003cbe:	1c28      	adds	r0, r5, #0
 8003cc0:	1c22      	adds	r2, r4, #0
 8003cc2:	f1ad fae7 	bl	0x81b1294
 8003cc6:	20b4      	movs	r0, #180	@ 0xb4
 8003cc8:	0100      	lsls	r0, r0, #4
 8003cca:	1829      	adds	r1, r5, r0
 8003ccc:	1c28      	adds	r0, r5, #0
 8003cce:	1c22      	adds	r2, r4, #0
 8003cd0:	f1ad fae0 	bl	0x81b1294
 8003cd4:	4640      	mov	r0, r8
 8003cd6:	7e81      	ldrb	r1, [r0, #26]
 8003cd8:	7f02      	ldrb	r2, [r0, #28]
 8003cda:	1876      	adds	r6, r6, r1
 8003cdc:	0636      	lsls	r6, r6, #24
 8003cde:	0e36      	lsrs	r6, r6, #24
 8003ce0:	1d10      	adds	r0, r2, #4
 8003ce2:	0600      	lsls	r0, r0, #24
 8003ce4:	0e00      	lsrs	r0, r0, #24
 8003ce6:	9000      	str	r0, [sp, #0]
 8003ce8:	4640      	mov	r0, r8
 8003cea:	1c33      	adds	r3, r6, #0
 8003cec:	f000 f80a 	bl	0x8003d04
 8003cf0:	b001      	add	sp, #4
 8003cf2:	bc38      	pop	{r3, r4, r5}
 8003cf4:	4698      	mov	r8, r3
 8003cf6:	46a1      	mov	r9, r4
 8003cf8:	46aa      	mov	sl, r5
 8003cfa:	bc70      	pop	{r4, r5, r6}
 8003cfc:	bc01      	pop	{r0}
 8003cfe:	4700      	bx	r0
 8003d00:	ffff 001f 	vshr.u32	d16, d15, #1
 8003d04:	b5f0      	push	{r4, r5, r6, r7, lr}
 8003d06:	4657      	mov	r7, sl
 8003d08:	464e      	mov	r6, r9
 8003d0a:	4645      	mov	r5, r8
 8003d0c:	b4e0      	push	{r5, r6, r7}
 8003d0e:	b081      	sub	sp, #4
 8003d10:	1c06      	adds	r6, r0, #0
 8003d12:	1c14      	adds	r4, r2, #0
 8003d14:	9d09      	ldr	r5, [sp, #36]	@ 0x24
 8003d16:	0609      	lsls	r1, r1, #24
 8003d18:	0e09      	lsrs	r1, r1, #24
 8003d1a:	4688      	mov	r8, r1
 8003d1c:	0624      	lsls	r4, r4, #24
 8003d1e:	0e24      	lsrs	r4, r4, #24
 8003d20:	061b      	lsls	r3, r3, #24
 8003d22:	0e1b      	lsrs	r3, r3, #24
 8003d24:	469a      	mov	sl, r3
 8003d26:	062d      	lsls	r5, r5, #24
 8003d28:	0e2d      	lsrs	r5, r5, #24
 8003d2a:	f7ff fcfd 	bl	0x8003728
 8003d2e:	0400      	lsls	r0, r0, #16
 8003d30:	0c00      	lsrs	r0, r0, #16
 8003d32:	4681      	mov	r9, r0
 8003d34:	6831      	ldr	r1, [r6, #0]
 8003d36:	0160      	lsls	r0, r4, #5
 8003d38:	4440      	add	r0, r8
 8003d3a:	0040      	lsls	r0, r0, #1
 8003d3c:	6909      	ldr	r1, [r1, #16]
 8003d3e:	1809      	adds	r1, r1, r0
 8003d40:	468c      	mov	ip, r1
 8003d42:	8af1      	ldrh	r1, [r6, #22]
 8003d44:	3102      	adds	r1, #2
 8003d46:	4441      	add	r1, r8
 8003d48:	0120      	lsls	r0, r4, #4
 8003d4a:	1b00      	subs	r0, r0, r4
 8003d4c:	0040      	lsls	r0, r0, #1
 8003d4e:	1809      	adds	r1, r1, r0
 8003d50:	0409      	lsls	r1, r1, #16
 8003d52:	0c09      	lsrs	r1, r1, #16
 8003d54:	9100      	str	r1, [sp, #0]
 8003d56:	2100      	movs	r1, #0
 8003d58:	1b2d      	subs	r5, r5, r4
 8003d5a:	42a9      	cmp	r1, r5
 8003d5c:	da1d      	bge.n	0x8003d9a
 8003d5e:	4650      	mov	r0, sl
 8003d60:	4642      	mov	r2, r8
 8003d62:	1a83      	subs	r3, r0, r2
 8003d64:	46a8      	mov	r8, r5
 8003d66:	2200      	movs	r2, #0
 8003d68:	1c4d      	adds	r5, r1, #1
 8003d6a:	429a      	cmp	r2, r3
 8003d6c:	da11      	bge.n	0x8003d92
 8003d6e:	014e      	lsls	r6, r1, #5
 8003d70:	0108      	lsls	r0, r1, #4
 8003d72:	1a40      	subs	r0, r0, r1
 8003d74:	0044      	lsls	r4, r0, #1
 8003d76:	18b0      	adds	r0, r6, r2
 8003d78:	0040      	lsls	r0, r0, #1
 8003d7a:	4460      	add	r0, ip
 8003d7c:	9f00      	ldr	r7, [sp, #0]
 8003d7e:	18b9      	adds	r1, r7, r2
 8003d80:	1909      	adds	r1, r1, r4
 8003d82:	464f      	mov	r7, r9
 8003d84:	4339      	orrs	r1, r7
 8003d86:	8001      	strh	r1, [r0, #0]
 8003d88:	1c50      	adds	r0, r2, #1
 8003d8a:	0600      	lsls	r0, r0, #24
 8003d8c:	0e02      	lsrs	r2, r0, #24
 8003d8e:	429a      	cmp	r2, r3
 8003d90:	dbf1      	blt.n	0x8003d76
 8003d92:	0628      	lsls	r0, r5, #24
 8003d94:	0e01      	lsrs	r1, r0, #24
 8003d96:	4541      	cmp	r1, r8
 8003d98:	dbe5      	blt.n	0x8003d66
 8003d9a:	b001      	add	sp, #4
 8003d9c:	bc38      	pop	{r3, r4, r5}
 8003d9e:	4698      	mov	r8, r3
 8003da0:	46a1      	mov	r9, r4
 8003da2:	46aa      	mov	sl, r5
 8003da4:	bcf0      	pop	{r4, r5, r6, r7}
 8003da6:	bc01      	pop	{r0}
 8003da8:	4700      	bx	r0
 8003daa:	0000      	movs	r0, r0
 8003dac:	b5f0      	push	{r4, r5, r6, r7, lr}
 8003dae:	b081      	sub	sp, #4
 8003db0:	1c05      	adds	r5, r0, #0
 8003db2:	f7ff fdd7 	bl	0x8003964
 8003db6:	0600      	lsls	r0, r0, #24
 8003db8:	0e00      	lsrs	r0, r0, #24
 8003dba:	2801      	cmp	r0, #1
 8003dbc:	d100      	bne.n	0x8003dc0
 8003dbe:	e093      	b.n	0x8003ee8
 8003dc0:	88e8      	ldrh	r0, [r5, #6]
 8003dc2:	0a00      	lsrs	r0, r0, #8
 8003dc4:	210f      	movs	r1, #15
 8003dc6:	4008      	ands	r0, r1
 8003dc8:	0180      	lsls	r0, r0, #6
 8003dca:	4905      	ldr	r1, [pc, #20]	@ (0x8003de0)
 8003dcc:	1847      	adds	r7, r0, r1
 8003dce:	7aa8      	ldrb	r0, [r5, #10]
 8003dd0:	2801      	cmp	r0, #1
 8003dd2:	d02f      	beq.n	0x8003e34
 8003dd4:	2801      	cmp	r0, #1
 8003dd6:	dc05      	bgt.n	0x8003de4
 8003dd8:	2800      	cmp	r0, #0
 8003dda:	d009      	beq.n	0x8003df0
 8003ddc:	e084      	b.n	0x8003ee8
 8003dde:	0000      	movs	r0, r0
 8003de0:	b2ac      	uxth	r4, r5
 8003de2:	081b      	lsrs	r3, r3, #32
 8003de4:	2802      	cmp	r0, #2
 8003de6:	d100      	bne.n	0x8003dea
 8003de8:	e07e      	b.n	0x8003ee8
 8003dea:	2803      	cmp	r0, #3
 8003dec:	d062      	beq.n	0x8003eb4
 8003dee:	e07b      	b.n	0x8003ee8
 8003df0:	682a      	ldr	r2, [r5, #0]
 8003df2:	8ae8      	ldrh	r0, [r5, #22]
 8003df4:	8b29      	ldrh	r1, [r5, #24]
 8003df6:	1840      	adds	r0, r0, r1
 8003df8:	0140      	lsls	r0, r0, #5
 8003dfa:	68d1      	ldr	r1, [r2, #12]
 8003dfc:	180c      	adds	r4, r1, r0
 8003dfe:	7b2a      	ldrb	r2, [r5, #12]
 8003e00:	7bab      	ldrb	r3, [r5, #14]
 8003e02:	7b68      	ldrb	r0, [r5, #13]
 8003e04:	9000      	str	r0, [sp, #0]
 8003e06:	1c38      	adds	r0, r7, #0
 8003e08:	1c21      	adds	r1, r4, #0
 8003e0a:	f7ff fd49 	bl	0x80038a0
 8003e0e:	1c38      	adds	r0, r7, #0
 8003e10:	3020      	adds	r0, #32
 8003e12:	1c21      	adds	r1, r4, #0
 8003e14:	3120      	adds	r1, #32
 8003e16:	7b2a      	ldrb	r2, [r5, #12]
 8003e18:	7bab      	ldrb	r3, [r5, #14]
 8003e1a:	7b6c      	ldrb	r4, [r5, #13]
 8003e1c:	9400      	str	r4, [sp, #0]
 8003e1e:	f7ff fd3f 	bl	0x80038a0
 8003e22:	8b2a      	ldrh	r2, [r5, #24]
 8003e24:	8ae8      	ldrh	r0, [r5, #22]
 8003e26:	1812      	adds	r2, r2, r0
 8003e28:	0412      	lsls	r2, r2, #16
 8003e2a:	0c16      	lsrs	r6, r2, #16
 8003e2c:	2180      	movs	r1, #128	@ 0x80
 8003e2e:	0249      	lsls	r1, r1, #9
 8003e30:	1852      	adds	r2, r2, r1
 8003e32:	e039      	b.n	0x8003ea8
 8003e34:	7ae8      	ldrb	r0, [r5, #11]
 8003e36:	2806      	cmp	r0, #6
 8003e38:	d81a      	bhi.n	0x8003e70
 8003e3a:	0080      	lsls	r0, r0, #2
 8003e3c:	4901      	ldr	r1, [pc, #4]	@ (0x8003e44)
 8003e3e:	1840      	adds	r0, r0, r1
 8003e40:	6800      	ldr	r0, [r0, #0]
 8003e42:	4687      	mov	pc, r0
 8003e44:	3e48      	subs	r6, #72	@ 0x48
 8003e46:	0800      	lsrs	r0, r0, #32
 8003e48:	3e64      	subs	r6, #100	@ 0x64
 8003e4a:	0800      	lsrs	r0, r0, #32
 8003e4c:	3e70      	subs	r6, #112	@ 0x70
 8003e4e:	0800      	lsrs	r0, r0, #32
 8003e50:	3e70      	subs	r6, #112	@ 0x70
 8003e52:	0800      	lsrs	r0, r0, #32
 8003e54:	3e64      	subs	r6, #100	@ 0x64
 8003e56:	0800      	lsrs	r0, r0, #32
 8003e58:	3e70      	subs	r6, #112	@ 0x70
 8003e5a:	0800      	lsrs	r0, r0, #32
 8003e5c:	3e70      	subs	r6, #112	@ 0x70
 8003e5e:	0800      	lsrs	r0, r0, #32
 8003e60:	3e70      	subs	r6, #112	@ 0x70
 8003e62:	0800      	lsrs	r0, r0, #32
 8003e64:	22fe      	movs	r2, #254	@ 0xfe
 8003e66:	0052      	lsls	r2, r2, #1
 8003e68:	1c10      	adds	r0, r2, #0
 8003e6a:	8ae9      	ldrh	r1, [r5, #22]
 8003e6c:	1840      	adds	r0, r0, r1
 8003e6e:	e001      	b.n	0x8003e74
 8003e70:	8ae8      	ldrh	r0, [r5, #22]
 8003e72:	30fe      	adds	r0, #254	@ 0xfe
 8003e74:	0400      	lsls	r0, r0, #16
 8003e76:	0c06      	lsrs	r6, r0, #16
 8003e78:	6828      	ldr	r0, [r5, #0]
 8003e7a:	0171      	lsls	r1, r6, #5
 8003e7c:	68c0      	ldr	r0, [r0, #12]
 8003e7e:	1844      	adds	r4, r0, r1
 8003e80:	7b2a      	ldrb	r2, [r5, #12]
 8003e82:	7bab      	ldrb	r3, [r5, #14]
 8003e84:	7b68      	ldrb	r0, [r5, #13]
 8003e86:	9000      	str	r0, [sp, #0]
 8003e88:	1c38      	adds	r0, r7, #0
 8003e8a:	1c21      	adds	r1, r4, #0
 8003e8c:	f7ff fd08 	bl	0x80038a0
 8003e90:	1c38      	adds	r0, r7, #0
 8003e92:	3020      	adds	r0, #32
 8003e94:	1c21      	adds	r1, r4, #0
 8003e96:	3120      	adds	r1, #32
 8003e98:	7b2a      	ldrb	r2, [r5, #12]
 8003e9a:	7bab      	ldrb	r3, [r5, #14]
 8003e9c:	7b6c      	ldrb	r4, [r5, #13]
 8003e9e:	9400      	str	r4, [sp, #0]
 8003ea0:	f7ff fcfe 	bl	0x80038a0
 8003ea4:	1c72      	adds	r2, r6, #1
 8003ea6:	0412      	lsls	r2, r2, #16
 8003ea8:	0c12      	lsrs	r2, r2, #16
 8003eaa:	1c28      	adds	r0, r5, #0
 8003eac:	1c31      	adds	r1, r6, #0
 8003eae:	f7ff fc15 	bl	0x80036dc
 8003eb2:	e019      	b.n	0x8003ee8
 8003eb4:	1c28      	adds	r0, r5, #0
 8003eb6:	f7ff fb13 	bl	0x80034e0
 8003eba:	1c04      	adds	r4, r0, #0
 8003ebc:	7b2a      	ldrb	r2, [r5, #12]
 8003ebe:	7bab      	ldrb	r3, [r5, #14]
 8003ec0:	7b68      	ldrb	r0, [r5, #13]
 8003ec2:	9000      	str	r0, [sp, #0]
 8003ec4:	1c38      	adds	r0, r7, #0
 8003ec6:	1c21      	adds	r1, r4, #0
 8003ec8:	f7ff fcea 	bl	0x80038a0
 8003ecc:	1c38      	adds	r0, r7, #0
 8003ece:	3020      	adds	r0, #32
 8003ed0:	22f0      	movs	r2, #240	@ 0xf0
 8003ed2:	0092      	lsls	r2, r2, #2
 8003ed4:	18a1      	adds	r1, r4, r2
 8003ed6:	7b2a      	ldrb	r2, [r5, #12]
 8003ed8:	7bab      	ldrb	r3, [r5, #14]
 8003eda:	7b6c      	ldrb	r4, [r5, #13]
 8003edc:	9400      	str	r4, [sp, #0]
 8003ede:	f7ff fcdf 	bl	0x80038a0
 8003ee2:	1c28      	adds	r0, r5, #0
 8003ee4:	f7ff fae0 	bl	0x80034a8
 8003ee8:	b001      	add	sp, #4
 8003eea:	bcf0      	pop	{r4, r5, r6, r7}
 8003eec:	bc01      	pop	{r0}
 8003eee:	4700      	bx	r0
 8003ef0:	b510      	push	{r4, lr}
 8003ef2:	1c04      	adds	r4, r0, #0
 8003ef4:	f7ff fd36 	bl	0x8003964
 8003ef8:	0600      	lsls	r0, r0, #24
 8003efa:	0e00      	lsrs	r0, r0, #24
 8003efc:	2801      	cmp	r0, #1
 8003efe:	d021      	beq.n	0x8003f44
 8003f00:	7aa0      	ldrb	r0, [r4, #10]
 8003f02:	2801      	cmp	r0, #1
 8003f04:	d00e      	beq.n	0x8003f24
 8003f06:	2801      	cmp	r0, #1
 8003f08:	dc02      	bgt.n	0x8003f10
 8003f0a:	2800      	cmp	r0, #0
 8003f0c:	d005      	beq.n	0x8003f1a
 8003f0e:	e019      	b.n	0x8003f44
 8003f10:	2802      	cmp	r0, #2
 8003f12:	d017      	beq.n	0x8003f44
 8003f14:	2803      	cmp	r0, #3
 8003f16:	d011      	beq.n	0x8003f3c
 8003f18:	e014      	b.n	0x8003f44
 8003f1a:	1c20      	adds	r0, r4, #0
 8003f1c:	2100      	movs	r1, #0
 8003f1e:	f7ff faff 	bl	0x8003520
 8003f22:	e00f      	b.n	0x8003f44
 8003f24:	4804      	ldr	r0, [pc, #16]	@ (0x8003f38)
 8003f26:	7ae1      	ldrb	r1, [r4, #11]
 8003f28:	0089      	lsls	r1, r1, #2
 8003f2a:	1809      	adds	r1, r1, r0
 8003f2c:	680a      	ldr	r2, [r1, #0]
 8003f2e:	1c20      	adds	r0, r4, #0
 8003f30:	2100      	movs	r1, #0
 8003f32:	f1ad f9d3 	bl	0x81b12dc
 8003f36:	e005      	b.n	0x8003f44
 8003f38:	b3bc      	cbz	r4, 0x8003faa
 8003f3a:	081b      	lsrs	r3, r3, #32
 8003f3c:	1c20      	adds	r0, r4, #0
 8003f3e:	2100      	movs	r1, #0
 8003f40:	f7ff fa90 	bl	0x8003464
 8003f44:	bc10      	pop	{r4}
 8003f46:	bc01      	pop	{r0}
 8003f48:	4700      	bx	r0
 8003f4a:	0000      	movs	r0, r0
 8003f4c:	b500      	push	{lr}
 8003f4e:	2100      	movs	r1, #0
 8003f50:	80c1      	strh	r1, [r0, #6]
 8003f52:	f7ff ff2b 	bl	0x8003dac
 8003f56:	bc01      	pop	{r0}
 8003f58:	4700      	bx	r0
 8003f5a:	0000      	movs	r0, r0
 8003f5c:	b500      	push	{lr}
 8003f5e:	2100      	movs	r1, #0
 8003f60:	80c1      	strh	r1, [r0, #6]
 8003f62:	f7ff ffc5 	bl	0x8003ef0
 8003f66:	bc01      	pop	{r0}
 8003f68:	4700      	bx	r0
 8003f6a:	0000      	movs	r0, r0
 8003f6c:	b570      	push	{r4, r5, r6, lr}
 8003f6e:	1c06      	adds	r6, r0, #0
 8003f70:	88f0      	ldrh	r0, [r6, #6]
 8003f72:	210f      	movs	r1, #15
 8003f74:	1c0d      	adds	r5, r1, #0
 8003f76:	4005      	ands	r5, r0
 8003f78:	0a04      	lsrs	r4, r0, #8
 8003f7a:	400c      	ands	r4, r1
 8003f7c:	3501      	adds	r5, #1
 8003f7e:	2d06      	cmp	r5, #6
 8003f80:	d109      	bne.n	0x8003f96
 8003f82:	2500      	movs	r5, #0
 8003f84:	3401      	adds	r4, #1
 8003f86:	2c03      	cmp	r4, #3
 8003f88:	d900      	bls.n	0x8003f8c
 8003f8a:	2400      	movs	r4, #0
 8003f8c:	0220      	lsls	r0, r4, #8
 8003f8e:	80f0      	strh	r0, [r6, #6]
 8003f90:	1c30      	adds	r0, r6, #0
 8003f92:	f7ff ff0b 	bl	0x8003dac
 8003f96:	0220      	lsls	r0, r4, #8
 8003f98:	4305      	orrs	r5, r0
 8003f9a:	80f5      	strh	r5, [r6, #6]
 8003f9c:	bc70      	pop	{r4, r5, r6}
 8003f9e:	bc01      	pop	{r0}
 8003fa0:	4700      	bx	r0
 8003fa2:	0000      	movs	r0, r0
 8003fa4:	b510      	push	{r4, lr}
 8003fa6:	1c04      	adds	r4, r0, #0
 8003fa8:	f7ff fcdc 	bl	0x8003964
 8003fac:	0600      	lsls	r0, r0, #24
 8003fae:	2800      	cmp	r0, #0
 8003fb0:	d006      	beq.n	0x8003fc0
 8003fb2:	7a60      	ldrb	r0, [r4, #9]
 8003fb4:	3801      	subs	r0, #1
 8003fb6:	7260      	strb	r0, [r4, #9]
 8003fb8:	0600      	lsls	r0, r0, #24
 8003fba:	2800      	cmp	r0, #0
 8003fbc:	d011      	beq.n	0x8003fe2
 8003fbe:	e005      	b.n	0x8003fcc
 8003fc0:	4805      	ldr	r0, [pc, #20]	@ (0x8003fd8)
 8003fc2:	8dc1      	ldrh	r1, [r0, #46]	@ 0x2e
 8003fc4:	2003      	movs	r0, #3
 8003fc6:	4008      	ands	r0, r1
 8003fc8:	2800      	cmp	r0, #0
 8003fca:	d107      	bne.n	0x8003fdc
 8003fcc:	1c20      	adds	r0, r4, #0
 8003fce:	f7ff ffcd 	bl	0x8003f6c
 8003fd2:	2000      	movs	r0, #0
 8003fd4:	e009      	b.n	0x8003fea
 8003fd6:	0000      	movs	r0, r0
 8003fd8:	16e0      	asrs	r0, r4, #27
 8003fda:	0300      	lsls	r0, r0, #12
 8003fdc:	2005      	movs	r0, #5
 8003fde:	f06e fa75 	bl	0x80724cc
 8003fe2:	1c20      	adds	r0, r4, #0
 8003fe4:	f7ff ffba 	bl	0x8003f5c
 8003fe8:	2001      	movs	r0, #1
 8003fea:	bc10      	pop	{r4}
 8003fec:	bc02      	pop	{r1}
 8003fee:	4708      	bx	r1
 8003ff0:	0609      	lsls	r1, r1, #24
 8003ff2:	0e09      	lsrs	r1, r1, #24
 8003ff4:	0612      	lsls	r2, r2, #24
 8003ff6:	6800      	ldr	r0, [r0, #0]
 8003ff8:	6900      	ldr	r0, [r0, #16]
 8003ffa:	0cd2      	lsrs	r2, r2, #19
 8003ffc:	1852      	adds	r2, r2, r1
 8003ffe:	0052      	lsls	r2, r2, #1
 8004000:	1812      	adds	r2, r2, r0
 8004002:	8810      	ldrh	r0, [r2, #0]
 8004004:	4770      	bx	lr
 8004006:	0000      	movs	r0, r0
 8004008:	b5f0      	push	{r4, r5, r6, r7, lr}
 800400a:	4647      	mov	r7, r8
 800400c:	b480      	push	{r7}
 800400e:	9c06      	ldr	r4, [sp, #24]
 8004010:	9d07      	ldr	r5, [sp, #28]
 8004012:	0409      	lsls	r1, r1, #16
 8004014:	0c0f      	lsrs	r7, r1, #16
 8004016:	0612      	lsls	r2, r2, #24
 8004018:	0e12      	lsrs	r2, r2, #24
 800401a:	4694      	mov	ip, r2
 800401c:	061b      	lsls	r3, r3, #24
 800401e:	0e1b      	lsrs	r3, r3, #24
 8004020:	4698      	mov	r8, r3
 8004022:	0624      	lsls	r4, r4, #24
 8004024:	0e26      	lsrs	r6, r4, #24
 8004026:	062d      	lsls	r5, r5, #24
 8004028:	0e2d      	lsrs	r5, r5, #24
 800402a:	6800      	ldr	r0, [r0, #0]
 800402c:	6904      	ldr	r4, [r0, #16]
 800402e:	4642      	mov	r2, r8
 8004030:	42aa      	cmp	r2, r5
 8004032:	d821      	bhi.n	0x8004078
 8004034:	4542      	cmp	r2, r8
 8004036:	d001      	beq.n	0x800403c
 8004038:	42aa      	cmp	r2, r5
 800403a:	d10e      	bne.n	0x800405a
 800403c:	4661      	mov	r1, ip
 800403e:	1c53      	adds	r3, r2, #1
 8004040:	45b4      	cmp	ip, r6
 8004042:	d815      	bhi.n	0x8004070
 8004044:	0152      	lsls	r2, r2, #5
 8004046:	1850      	adds	r0, r2, r1
 8004048:	0040      	lsls	r0, r0, #1
 800404a:	1900      	adds	r0, r0, r4
 800404c:	8007      	strh	r7, [r0, #0]
 800404e:	1c48      	adds	r0, r1, #1
 8004050:	0600      	lsls	r0, r0, #24
 8004052:	0e01      	lsrs	r1, r0, #24
 8004054:	42b1      	cmp	r1, r6
 8004056:	d9f6      	bls.n	0x8004046
 8004058:	e00a      	b.n	0x8004070
 800405a:	0151      	lsls	r1, r2, #5
 800405c:	4663      	mov	r3, ip
 800405e:	18c8      	adds	r0, r1, r3
 8004060:	0040      	lsls	r0, r0, #1
 8004062:	1900      	adds	r0, r0, r4
 8004064:	8007      	strh	r7, [r0, #0]
 8004066:	1989      	adds	r1, r1, r6
 8004068:	0049      	lsls	r1, r1, #1
 800406a:	1909      	adds	r1, r1, r4
 800406c:	800f      	strh	r7, [r1, #0]
 800406e:	1c53      	adds	r3, r2, #1
 8004070:	0618      	lsls	r0, r3, #24
 8004072:	0e02      	lsrs	r2, r0, #24
 8004074:	42aa      	cmp	r2, r5
 8004076:	d9dd      	bls.n	0x8004034
 8004078:	bc08      	pop	{r3}
 800407a:	4698      	mov	r8, r3
 800407c:	bcf0      	pop	{r4, r5, r6, r7}
 800407e:	bc01      	pop	{r0}
 8004080:	4700      	bx	r0
 8004082:	0000      	movs	r0, r0
 8004084:	b570      	push	{r4, r5, r6, lr}
 8004086:	b082      	sub	sp, #8
 8004088:	1c0e      	adds	r6, r1, #0
 800408a:	9c06      	ldr	r4, [sp, #24]
 800408c:	9d07      	ldr	r5, [sp, #28]
 800408e:	0436      	lsls	r6, r6, #16
 8004090:	0612      	lsls	r2, r2, #24
 8004092:	0e12      	lsrs	r2, r2, #24
 8004094:	061b      	lsls	r3, r3, #24
 8004096:	0e1b      	lsrs	r3, r3, #24
 8004098:	0624      	lsls	r4, r4, #24
 800409a:	0e24      	lsrs	r4, r4, #24
 800409c:	062d      	lsls	r5, r5, #24
 800409e:	0e2d      	lsrs	r5, r5, #24
 80040a0:	7bc1      	ldrb	r1, [r0, #15]
 80040a2:	0709      	lsls	r1, r1, #28
 80040a4:	4331      	orrs	r1, r6
 80040a6:	0c09      	lsrs	r1, r1, #16
 80040a8:	9400      	str	r4, [sp, #0]
 80040aa:	9501      	str	r5, [sp, #4]
 80040ac:	f7ff ffac 	bl	0x8004008
 80040b0:	b002      	add	sp, #8
 80040b2:	bc70      	pop	{r4, r5, r6}
 80040b4:	bc01      	pop	{r0}
 80040b6:	4700      	bx	r0
 80040b8:	b5f0      	push	{r4, r5, r6, r7, lr}
 80040ba:	9c05      	ldr	r4, [sp, #20]
 80040bc:	9d06      	ldr	r5, [sp, #24]
 80040be:	0409      	lsls	r1, r1, #16
 80040c0:	0c0f      	lsrs	r7, r1, #16
 80040c2:	0612      	lsls	r2, r2, #24
 80040c4:	061b      	lsls	r3, r3, #24
 80040c6:	0e1b      	lsrs	r3, r3, #24
 80040c8:	469c      	mov	ip, r3
 80040ca:	0624      	lsls	r4, r4, #24
 80040cc:	0e26      	lsrs	r6, r4, #24
 80040ce:	062d      	lsls	r5, r5, #24
 80040d0:	0e2d      	lsrs	r5, r5, #24
 80040d2:	6800      	ldr	r0, [r0, #0]
 80040d4:	6904      	ldr	r4, [r0, #16]
 80040d6:	0e12      	lsrs	r2, r2, #24
 80040d8:	42b2      	cmp	r2, r6
 80040da:	d811      	bhi.n	0x8004100
 80040dc:	4661      	mov	r1, ip
 80040de:	1c53      	adds	r3, r2, #1
 80040e0:	42a9      	cmp	r1, r5
 80040e2:	d809      	bhi.n	0x80040f8
 80040e4:	0148      	lsls	r0, r1, #5
 80040e6:	1880      	adds	r0, r0, r2
 80040e8:	0040      	lsls	r0, r0, #1
 80040ea:	1900      	adds	r0, r0, r4
 80040ec:	8007      	strh	r7, [r0, #0]
 80040ee:	1c48      	adds	r0, r1, #1
 80040f0:	0600      	lsls	r0, r0, #24
 80040f2:	0e01      	lsrs	r1, r0, #24
 80040f4:	42a9      	cmp	r1, r5
 80040f6:	d9f5      	bls.n	0x80040e4
 80040f8:	0618      	lsls	r0, r3, #24
 80040fa:	0e02      	lsrs	r2, r0, #24
 80040fc:	42b2      	cmp	r2, r6
 80040fe:	d9ed      	bls.n	0x80040dc
 8004100:	bcf0      	pop	{r4, r5, r6, r7}
 8004102:	bc01      	pop	{r0}
 8004104:	4700      	bx	r0
 8004106:	0000      	movs	r0, r0
 8004108:	b570      	push	{r4, r5, r6, lr}
 800410a:	b082      	sub	sp, #8
 800410c:	1c0e      	adds	r6, r1, #0
 800410e:	9c06      	ldr	r4, [sp, #24]
 8004110:	9d07      	ldr	r5, [sp, #28]
 8004112:	0436      	lsls	r6, r6, #16
 8004114:	0612      	lsls	r2, r2, #24
 8004116:	0e12      	lsrs	r2, r2, #24
 8004118:	061b      	lsls	r3, r3, #24
 800411a:	0e1b      	lsrs	r3, r3, #24
 800411c:	0624      	lsls	r4, r4, #24
 800411e:	0e24      	lsrs	r4, r4, #24
 8004120:	062d      	lsls	r5, r5, #24
 8004122:	0e2d      	lsrs	r5, r5, #24
 8004124:	7bc1      	ldrb	r1, [r0, #15]
 8004126:	0709      	lsls	r1, r1, #28
 8004128:	4331      	orrs	r1, r6
 800412a:	0c09      	lsrs	r1, r1, #16
 800412c:	9400      	str	r4, [sp, #0]
 800412e:	9501      	str	r5, [sp, #4]
 8004130:	f7ff ffc2 	bl	0x80040b8
 8004134:	b002      	add	sp, #8
 8004136:	bc70      	pop	{r4, r5, r6}
 8004138:	bc01      	pop	{r0}
 800413a:	4700      	bx	r0
 800413c:	b530      	push	{r4, r5, lr}
 800413e:	b082      	sub	sp, #8
 8004140:	1c0c      	adds	r4, r1, #0
 8004142:	1c15      	adds	r5, r2, #0
 8004144:	9905      	ldr	r1, [sp, #20]
 8004146:	0624      	lsls	r4, r4, #24
 8004148:	0e24      	lsrs	r4, r4, #24
 800414a:	062d      	lsls	r5, r5, #24
 800414c:	0e2d      	lsrs	r5, r5, #24
 800414e:	061b      	lsls	r3, r3, #24
 8004150:	0e1b      	lsrs	r3, r3, #24
 8004152:	0609      	lsls	r1, r1, #24
 8004154:	0e09      	lsrs	r1, r1, #24
 8004156:	9300      	str	r3, [sp, #0]
 8004158:	9101      	str	r1, [sp, #4]
 800415a:	2100      	movs	r1, #0
 800415c:	1c22      	adds	r2, r4, #0
 800415e:	1c2b      	adds	r3, r5, #0
 8004160:	f7ff ffd2 	bl	0x8004108
 8004164:	b002      	add	sp, #8
 8004166:	bc30      	pop	{r4, r5}
 8004168:	bc01      	pop	{r0}
 800416a:	4700      	bx	r0
 800416c:	b570      	push	{r4, r5, r6, lr}
 800416e:	464e      	mov	r6, r9
 8004170:	4645      	mov	r5, r8
 8004172:	b460      	push	{r5, r6}
 8004174:	b082      	sub	sp, #8
 8004176:	4681      	mov	r9, r0
 8004178:	1c0e      	adds	r6, r1, #0
 800417a:	4690      	mov	r8, r2
 800417c:	1c1c      	adds	r4, r3, #0
 800417e:	9d08      	ldr	r5, [sp, #32]
 8004180:	0636      	lsls	r6, r6, #24
 8004182:	0e36      	lsrs	r6, r6, #24
 8004184:	4640      	mov	r0, r8
 8004186:	0600      	lsls	r0, r0, #24
 8004188:	0e00      	lsrs	r0, r0, #24
 800418a:	4680      	mov	r8, r0
 800418c:	0624      	lsls	r4, r4, #24
 800418e:	0e24      	lsrs	r4, r4, #24
 8004190:	062d      	lsls	r5, r5, #24
 8004192:	0e2d      	lsrs	r5, r5, #24
 8004194:	4648      	mov	r0, r9
 8004196:	f000 f811 	bl	0x80041bc
 800419a:	1c01      	adds	r1, r0, #0
 800419c:	0409      	lsls	r1, r1, #16
 800419e:	0c09      	lsrs	r1, r1, #16
 80041a0:	9400      	str	r4, [sp, #0]
 80041a2:	9501      	str	r5, [sp, #4]
 80041a4:	4648      	mov	r0, r9
 80041a6:	1c32      	adds	r2, r6, #0
 80041a8:	4643      	mov	r3, r8
 80041aa:	f7ff ffad 	bl	0x8004108
 80041ae:	b002      	add	sp, #8
 80041b0:	bc18      	pop	{r3, r4}
 80041b2:	4698      	mov	r8, r3
 80041b4:	46a1      	mov	r9, r4
 80041b6:	bc70      	pop	{r4, r5, r6}
 80041b8:	bc01      	pop	{r0}
 80041ba:	4700      	bx	r0
 80041bc:	b500      	push	{lr}
 80041be:	1c02      	adds	r2, r0, #0
 80041c0:	7a90      	ldrb	r0, [r2, #10]
 80041c2:	2801      	cmp	r0, #1
 80041c4:	d009      	beq.n	0x80041da
 80041c6:	2801      	cmp	r0, #1
 80041c8:	dc02      	bgt.n	0x80041d0
 80041ca:	2800      	cmp	r0, #0
 80041cc:	d021      	beq.n	0x8004212
 80041ce:	e027      	b.n	0x8004220
 80041d0:	2802      	cmp	r0, #2
 80041d2:	d025      	beq.n	0x8004220
 80041d4:	2803      	cmp	r0, #3
 80041d6:	d01e      	beq.n	0x8004216
 80041d8:	e022      	b.n	0x8004220
 80041da:	7ad0      	ldrb	r0, [r2, #11]
 80041dc:	2806      	cmp	r0, #6
 80041de:	d81f      	bhi.n	0x8004220
 80041e0:	0080      	lsls	r0, r0, #2
 80041e2:	4902      	ldr	r1, [pc, #8]	@ (0x80041ec)
 80041e4:	1840      	adds	r0, r0, r1
 80041e6:	6800      	ldr	r0, [r0, #0]
 80041e8:	4687      	mov	pc, r0
 80041ea:	0000      	movs	r0, r0
 80041ec:	41f0      	rors	r0, r6
 80041ee:	0800      	lsrs	r0, r0, #32
 80041f0:	4212      	tst	r2, r2
 80041f2:	0800      	lsrs	r0, r0, #32
 80041f4:	420c      	tst	r4, r1
 80041f6:	0800      	lsrs	r0, r0, #32
 80041f8:	420c      	tst	r4, r1
 80041fa:	0800      	lsrs	r0, r0, #32
 80041fc:	4212      	tst	r2, r2
 80041fe:	0800      	lsrs	r0, r0, #32
 8004200:	420c      	tst	r4, r1
 8004202:	0800      	lsrs	r0, r0, #32
 8004204:	420c      	tst	r4, r1
 8004206:	0800      	lsrs	r0, r0, #32
 8004208:	4212      	tst	r2, r2
 800420a:	0800      	lsrs	r0, r0, #32
 800420c:	8ad0      	ldrh	r0, [r2, #22]
 800420e:	30d4      	adds	r0, #212	@ 0xd4
 8004210:	e003      	b.n	0x800421a
 8004212:	8ad0      	ldrh	r0, [r2, #22]
 8004214:	e005      	b.n	0x8004222
 8004216:	8ad0      	ldrh	r0, [r2, #22]
 8004218:	3001      	adds	r0, #1
 800421a:	0400      	lsls	r0, r0, #16
 800421c:	0c00      	lsrs	r0, r0, #16
 800421e:	e000      	b.n	0x8004222
 8004220:	2000      	movs	r0, #0
 8004222:	bc02      	pop	{r1}
 8004224:	4708      	bx	r1
 8004226:	0000      	movs	r0, r0
 8004228:	b500      	push	{lr}
 800422a:	1c02      	adds	r2, r0, #0
 800422c:	4900      	ldr	r1, [pc, #0]	@ (0x8004230)
 800422e:	e007      	b.n	0x8004240
 8004230:	b8d4      			@ <UNDEFINED> instruction: 0xb8d4
 8004232:	081b      	lsrs	r3, r3, #32
 8004234:	6848      	ldr	r0, [r1, #4]
 8004236:	4290      	cmp	r0, r2
 8004238:	d101      	bne.n	0x800423e
 800423a:	6808      	ldr	r0, [r1, #0]
 800423c:	e004      	b.n	0x8004248
 800423e:	3108      	adds	r1, #8
 8004240:	6808      	ldr	r0, [r1, #0]
 8004242:	2800      	cmp	r0, #0
 8004244:	d1f6      	bne.n	0x8004234
 8004246:	2000      	movs	r0, #0
 8004248:	bc02      	pop	{r1}
 800424a:	4708      	bx	r1
 800424c:	6800      	ldr	r0, [r0, #0]
 800424e:	6900      	ldr	r0, [r0, #16]
 8004250:	4770      	bx	lr
 8004252:	0000      	movs	r0, r0
 8004254:	6800      	ldr	r0, [r0, #0]
 8004256:	68c0      	ldr	r0, [r0, #12]
 8004258:	4770      	bx	lr
 800425a:	0000      	movs	r0, r0
 800425c:	b530      	push	{r4, r5, lr}
 800425e:	1c04      	adds	r4, r0, #0
 8004260:	2505      	movs	r5, #5
 8004262:	2300      	movs	r3, #0
 8004264:	18e2      	adds	r2, r4, r3
 8004266:	18c8      	adds	r0, r1, r3
 8004268:	7800      	ldrb	r0, [r0, #0]
 800426a:	7010      	strb	r0, [r2, #0]
 800426c:	0600      	lsls	r0, r0, #24
 800426e:	0e00      	lsrs	r0, r0, #24
 8004270:	28ff      	cmp	r0, #255	@ 0xff
 8004272:	d101      	bne.n	0x8004278
 8004274:	1c10      	adds	r0, r2, #0
 8004276:	e007      	b.n	0x8004288
 8004278:	1c58      	adds	r0, r3, #1
 800427a:	0600      	lsls	r0, r0, #24
 800427c:	0e03      	lsrs	r3, r0, #24
 800427e:	42ab      	cmp	r3, r5
 8004280:	d3f0      	bcc.n	0x8004264
 8004282:	18e0      	adds	r0, r4, r3
 8004284:	21ff      	movs	r1, #255	@ 0xff
 8004286:	7001      	strb	r1, [r0, #0]
 8004288:	bc30      	pop	{r4, r5}
 800428a:	bc02      	pop	{r1}
 800428c:	4708      	bx	r1
 800428e:	0000      	movs	r0, r0
 8004290:	b510      	push	{r4, lr}
 8004292:	1c03      	adds	r3, r0, #0
 8004294:	2405      	movs	r4, #5
 8004296:	2200      	movs	r2, #0
 8004298:	1899      	adds	r1, r3, r2
 800429a:	7808      	ldrb	r0, [r1, #0]
 800429c:	28ff      	cmp	r0, #255	@ 0xff
 800429e:	d101      	bne.n	0x80042a4
 80042a0:	1c08      	adds	r0, r1, #0
 80042a2:	e007      	b.n	0x80042b4
 80042a4:	1c50      	adds	r0, r2, #1
 80042a6:	0600      	lsls	r0, r0, #24
 80042a8:	0e02      	lsrs	r2, r0, #24
 80042aa:	42a2      	cmp	r2, r4
 80042ac:	d3f4      	bcc.n	0x8004298
 80042ae:	1898      	adds	r0, r3, r2
 80042b0:	21ff      	movs	r1, #255	@ 0xff
 80042b2:	7001      	strb	r1, [r0, #0]
 80042b4:	bc10      	pop	{r4}
 80042b6:	bc02      	pop	{r1}
 80042b8:	4708      	bx	r1
 80042ba:	0000      	movs	r0, r0
 80042bc:	b510      	push	{r4, lr}
 80042be:	1c04      	adds	r4, r0, #0
 80042c0:	2300      	movs	r3, #0
 80042c2:	18e2      	adds	r2, r4, r3
 80042c4:	18c8      	adds	r0, r1, r3
 80042c6:	7800      	ldrb	r0, [r0, #0]
 80042c8:	7010      	strb	r0, [r2, #0]
 80042ca:	0600      	lsls	r0, r0, #24
 80042cc:	0e00      	lsrs	r0, r0, #24
 80042ce:	28ff      	cmp	r0, #255	@ 0xff
 80042d0:	d101      	bne.n	0x80042d6
 80042d2:	1c10      	adds	r0, r2, #0
 80042d4:	e005      	b.n	0x80042e2
 80042d6:	3301      	adds	r3, #1
 80042d8:	2b07      	cmp	r3, #7
 80042da:	ddf2      	ble.n	0x80042c2
 80042dc:	18e0      	adds	r0, r4, r3
 80042de:	21ff      	movs	r1, #255	@ 0xff
 80042e0:	7001      	strb	r1, [r0, #0]
 80042e2:	bc10      	pop	{r4}
 80042e4:	bc02      	pop	{r1}
 80042e6:	4708      	bx	r1
 80042e8:	b500      	push	{lr}
 80042ea:	1c03      	adds	r3, r0, #0
 80042ec:	e002      	b.n	0x80042f4
 80042ee:	701a      	strb	r2, [r3, #0]
 80042f0:	3301      	adds	r3, #1
 80042f2:	3101      	adds	r1, #1
 80042f4:	780a      	ldrb	r2, [r1, #0]
 80042f6:	1c10      	adds	r0, r2, #0
 80042f8:	28ff      	cmp	r0, #255	@ 0xff
 80042fa:	d1f8      	bne.n	0x80042ee
 80042fc:	20ff      	movs	r0, #255	@ 0xff
 80042fe:	7018      	strb	r0, [r3, #0]
 8004300:	1c18      	adds	r0, r3, #0
 8004302:	bc02      	pop	{r1}
 8004304:	4708      	bx	r1
 8004306:	0000      	movs	r0, r0
 8004308:	b500      	push	{lr}
 800430a:	1c02      	adds	r2, r0, #0
 800430c:	e000      	b.n	0x8004310
 800430e:	3201      	adds	r2, #1
 8004310:	7810      	ldrb	r0, [r2, #0]
 8004312:	28ff      	cmp	r0, #255	@ 0xff
 8004314:	d1fb      	bne.n	0x800430e
 8004316:	1c10      	adds	r0, r2, #0
 8004318:	f7ff ffe6 	bl	0x80042e8
 800431c:	bc02      	pop	{r1}
 800431e:	4708      	bx	r1
 8004320:	b570      	push	{r4, r5, r6, lr}
 8004322:	1c04      	adds	r4, r0, #0
 8004324:	1c0e      	adds	r6, r1, #0
 8004326:	0612      	lsls	r2, r2, #24
 8004328:	0e15      	lsrs	r5, r2, #24
 800432a:	2300      	movs	r3, #0
 800432c:	1c28      	adds	r0, r5, #0
 800432e:	4283      	cmp	r3, r0
 8004330:	d209      	bcs.n	0x8004346
 8004332:	1c02      	adds	r2, r0, #0
 8004334:	18e1      	adds	r1, r4, r3
 8004336:	18f0      	adds	r0, r6, r3
 8004338:	7800      	ldrb	r0, [r0, #0]
 800433a:	7008      	strb	r0, [r1, #0]
 800433c:	1c58      	adds	r0, r3, #1
 800433e:	0400      	lsls	r0, r0, #16
 8004340:	0c03      	lsrs	r3, r0, #16
 8004342:	4293      	cmp	r3, r2
 8004344:	d3f6      	bcc.n	0x8004334
 8004346:	1960      	adds	r0, r4, r5
 8004348:	bc70      	pop	{r4, r5, r6}
 800434a:	bc02      	pop	{r1}
 800434c:	4708      	bx	r1
 800434e:	0000      	movs	r0, r0
 8004350:	b500      	push	{lr}
 8004352:	1c03      	adds	r3, r0, #0
 8004354:	0612      	lsls	r2, r2, #24
 8004356:	0e12      	lsrs	r2, r2, #24
 8004358:	e000      	b.n	0x800435c
 800435a:	3301      	adds	r3, #1
 800435c:	7818      	ldrb	r0, [r3, #0]
 800435e:	28ff      	cmp	r0, #255	@ 0xff
 8004360:	d1fb      	bne.n	0x800435a
 8004362:	1c18      	adds	r0, r3, #0
 8004364:	f7ff ffdc 	bl	0x8004320
 8004368:	bc02      	pop	{r1}
 800436a:	4708      	bx	r1
 800436c:	b500      	push	{lr}
 800436e:	1c02      	adds	r2, r0, #0
 8004370:	2100      	movs	r1, #0
 8004372:	7810      	ldrb	r0, [r2, #0]
 8004374:	28ff      	cmp	r0, #255	@ 0xff
 8004376:	d006      	beq.n	0x8004386
 8004378:	1c48      	adds	r0, r1, #1
 800437a:	0400      	lsls	r0, r0, #16
 800437c:	0c01      	lsrs	r1, r0, #16
 800437e:	1850      	adds	r0, r2, r1
 8004380:	7800      	ldrb	r0, [r0, #0]
 8004382:	28ff      	cmp	r0, #255	@ 0xff
 8004384:	d1f8      	bne.n	0x8004378
 8004386:	1c08      	adds	r0, r1, #0
 8004388:	bc02      	pop	{r1}
 800438a:	4708      	bx	r1
 800438c:	b500      	push	{lr}
 800438e:	1c02      	adds	r2, r0, #0
 8004390:	e005      	b.n	0x800439e
 8004392:	28ff      	cmp	r0, #255	@ 0xff
 8004394:	d101      	bne.n	0x800439a
 8004396:	2000      	movs	r0, #0
 8004398:	e008      	b.n	0x80043ac
 800439a:	3201      	adds	r2, #1
 800439c:	3101      	adds	r1, #1
 800439e:	7810      	ldrb	r0, [r2, #0]
 80043a0:	780b      	ldrb	r3, [r1, #0]
 80043a2:	4298      	cmp	r0, r3
 80043a4:	d0f5      	beq.n	0x8004392
 80043a6:	7810      	ldrb	r0, [r2, #0]
 80043a8:	7809      	ldrb	r1, [r1, #0]
 80043aa:	1a40      	subs	r0, r0, r1
 80043ac:	bc02      	pop	{r1}
 80043ae:	4708      	bx	r1
 80043b0:	b510      	push	{r4, lr}
 80043b2:	1c03      	adds	r3, r0, #0
 80043b4:	e008      	b.n	0x80043c8
 80043b6:	28ff      	cmp	r0, #255	@ 0xff
 80043b8:	d004      	beq.n	0x80043c4
 80043ba:	3301      	adds	r3, #1
 80043bc:	3101      	adds	r1, #1
 80043be:	3a01      	subs	r2, #1
 80043c0:	2a00      	cmp	r2, #0
 80043c2:	d101      	bne.n	0x80043c8
 80043c4:	2000      	movs	r0, #0
 80043c6:	e006      	b.n	0x80043d6
 80043c8:	7818      	ldrb	r0, [r3, #0]
 80043ca:	780c      	ldrb	r4, [r1, #0]
 80043cc:	42a0      	cmp	r0, r4
 80043ce:	d0f2      	beq.n	0x80043b6
 80043d0:	7818      	ldrb	r0, [r3, #0]
 80043d2:	7809      	ldrb	r1, [r1, #0]
 80043d4:	1a40      	subs	r0, r0, r1
 80043d6:	bc10      	pop	{r4}
 80043d8:	bc02      	pop	{r1}
 80043da:	4708      	bx	r1
 80043dc:	b5f0      	push	{r4, r5, r6, r7, lr}
 80043de:	4647      	mov	r7, r8
 80043e0:	b480      	push	{r7}
 80043e2:	1c04      	adds	r4, r0, #0
 80043e4:	1c0e      	adds	r6, r1, #0
 80043e6:	061b      	lsls	r3, r3, #24
 80043e8:	4810      	ldr	r0, [pc, #64]	@ (0x800442c)
 80043ea:	0d9b      	lsrs	r3, r3, #22
 80043ec:	3b04      	subs	r3, #4
 80043ee:	181b      	adds	r3, r3, r0
 80043f0:	6818      	ldr	r0, [r3, #0]
 80043f2:	2700      	movs	r7, #0
 80043f4:	2a01      	cmp	r2, #1
 80043f6:	d100      	bne.n	0x80043fa
 80043f8:	2702      	movs	r7, #2
 80043fa:	2a02      	cmp	r2, #2
 80043fc:	d100      	bne.n	0x8004400
 80043fe:	2701      	movs	r7, #1
 8004400:	1c05      	adds	r5, r0, #0
 8004402:	2d00      	cmp	r5, #0
 8004404:	dd32      	ble.n	0x800446c
 8004406:	480a      	ldr	r0, [pc, #40]	@ (0x8004430)
 8004408:	4680      	mov	r8, r0
 800440a:	1c30      	adds	r0, r6, #0
 800440c:	1c29      	adds	r1, r5, #0
 800440e:	f1ac ff7f 	bl	0x81b1310
 8004412:	0400      	lsls	r0, r0, #16
 8004414:	0c02      	lsrs	r2, r0, #16
 8004416:	1c28      	adds	r0, r5, #0
 8004418:	4350      	muls	r0, r2
 800441a:	1a31      	subs	r1, r6, r0
 800441c:	2f01      	cmp	r7, #1
 800441e:	d109      	bne.n	0x8004434
 8004420:	1c23      	adds	r3, r4, #0
 8004422:	3401      	adds	r4, #1
 8004424:	2a09      	cmp	r2, #9
 8004426:	d90e      	bls.n	0x8004446
 8004428:	e011      	b.n	0x800444e
 800442a:	0000      	movs	r0, r0
 800442c:	ba94      	hlt	0x0014
 800442e:	081b      	lsrs	r3, r3, #32
 8004430:	ba84      	hlt	0x0004
 8004432:	081b      	lsrs	r3, r3, #32
 8004434:	2a00      	cmp	r2, #0
 8004436:	d101      	bne.n	0x800443c
 8004438:	2d01      	cmp	r5, #1
 800443a:	d10b      	bne.n	0x8004454
 800443c:	2701      	movs	r7, #1
 800443e:	1c23      	adds	r3, r4, #0
 8004440:	3401      	adds	r4, #1
 8004442:	2a09      	cmp	r2, #9
 8004444:	d803      	bhi.n	0x800444e
 8004446:	4646      	mov	r6, r8
 8004448:	1990      	adds	r0, r2, r6
 800444a:	7800      	ldrb	r0, [r0, #0]
 800444c:	e000      	b.n	0x8004450
 800444e:	20ac      	movs	r0, #172	@ 0xac
 8004450:	7018      	strb	r0, [r3, #0]
 8004452:	e003      	b.n	0x800445c
 8004454:	2f02      	cmp	r7, #2
 8004456:	d101      	bne.n	0x800445c
 8004458:	7022      	strb	r2, [r4, #0]
 800445a:	3401      	adds	r4, #1
 800445c:	1c0e      	adds	r6, r1, #0
 800445e:	1c28      	adds	r0, r5, #0
 8004460:	210a      	movs	r1, #10
 8004462:	f1ac ff55 	bl	0x81b1310
 8004466:	1c05      	adds	r5, r0, #0
 8004468:	2d00      	cmp	r5, #0
 800446a:	dcce      	bgt.n	0x800440a
 800446c:	20ff      	movs	r0, #255	@ 0xff
 800446e:	7020      	strb	r0, [r4, #0]
 8004470:	1c20      	adds	r0, r4, #0
 8004472:	bc08      	pop	{r3}
 8004474:	4698      	mov	r8, r3
 8004476:	bcf0      	pop	{r4, r5, r6, r7}
 8004478:	bc02      	pop	{r1}
 800447a:	4708      	bx	r1
 800447c:	b5f0      	push	{r4, r5, r6, r7, lr}
 800447e:	4647      	mov	r7, r8
 8004480:	b480      	push	{r7}
 8004482:	b081      	sub	sp, #4
 8004484:	1c06      	adds	r6, r0, #0
 8004486:	1c0f      	adds	r7, r1, #0
 8004488:	061b      	lsls	r3, r3, #24
 800448a:	0e1b      	lsrs	r3, r3, #24
 800448c:	2101      	movs	r1, #1
 800448e:	2001      	movs	r0, #1
 8004490:	4299      	cmp	r1, r3
 8004492:	d205      	bcs.n	0x80044a0
 8004494:	0109      	lsls	r1, r1, #4
 8004496:	3001      	adds	r0, #1
 8004498:	0600      	lsls	r0, r0, #24
 800449a:	0e00      	lsrs	r0, r0, #24
 800449c:	4298      	cmp	r0, r3
 800449e:	d3f9      	bcc.n	0x8004494
 80044a0:	2300      	movs	r3, #0
 80044a2:	2a01      	cmp	r2, #1
 80044a4:	d100      	bne.n	0x80044a8
 80044a6:	2302      	movs	r3, #2
 80044a8:	2a02      	cmp	r2, #2
 80044aa:	d100      	bne.n	0x80044ae
 80044ac:	2301      	movs	r3, #1
 80044ae:	1c0d      	adds	r5, r1, #0
 80044b0:	2d00      	cmp	r5, #0
 80044b2:	dd33      	ble.n	0x800451c
 80044b4:	480a      	ldr	r0, [pc, #40]	@ (0x80044e0)
 80044b6:	4680      	mov	r8, r0
 80044b8:	1c38      	adds	r0, r7, #0
 80044ba:	1c29      	adds	r1, r5, #0
 80044bc:	9300      	str	r3, [sp, #0]
 80044be:	f1ac ff27 	bl	0x81b1310
 80044c2:	1c04      	adds	r4, r0, #0
 80044c4:	1c38      	adds	r0, r7, #0
 80044c6:	1c29      	adds	r1, r5, #0
 80044c8:	f1ac ffaa 	bl	0x81b1420
 80044cc:	1c01      	adds	r1, r0, #0
 80044ce:	9b00      	ldr	r3, [sp, #0]
 80044d0:	2b01      	cmp	r3, #1
 80044d2:	d107      	bne.n	0x80044e4
 80044d4:	1c32      	adds	r2, r6, #0
 80044d6:	3601      	adds	r6, #1
 80044d8:	2c0f      	cmp	r4, #15
 80044da:	d90c      	bls.n	0x80044f6
 80044dc:	e00f      	b.n	0x80044fe
 80044de:	0000      	movs	r0, r0
 80044e0:	ba84      	hlt	0x0004
 80044e2:	081b      	lsrs	r3, r3, #32
 80044e4:	2c00      	cmp	r4, #0
 80044e6:	d101      	bne.n	0x80044ec
 80044e8:	2d01      	cmp	r5, #1
 80044ea:	d10b      	bne.n	0x8004504
 80044ec:	2301      	movs	r3, #1
 80044ee:	1c32      	adds	r2, r6, #0
 80044f0:	3601      	adds	r6, #1
 80044f2:	2c0f      	cmp	r4, #15
 80044f4:	d803      	bhi.n	0x80044fe
 80044f6:	4647      	mov	r7, r8
 80044f8:	19e0      	adds	r0, r4, r7
 80044fa:	7800      	ldrb	r0, [r0, #0]
 80044fc:	e000      	b.n	0x8004500
 80044fe:	20ac      	movs	r0, #172	@ 0xac
 8004500:	7010      	strb	r0, [r2, #0]
 8004502:	e003      	b.n	0x800450c
 8004504:	2b02      	cmp	r3, #2
 8004506:	d101      	bne.n	0x800450c
 8004508:	7034      	strb	r4, [r6, #0]
 800450a:	3601      	adds	r6, #1
 800450c:	1c0f      	adds	r7, r1, #0
 800450e:	1c28      	adds	r0, r5, #0
 8004510:	2d00      	cmp	r5, #0
 8004512:	da00      	bge.n	0x8004516
 8004514:	300f      	adds	r0, #15
 8004516:	1105      	asrs	r5, r0, #4
 8004518:	2d00      	cmp	r5, #0
 800451a:	dccd      	bgt.n	0x80044b8
 800451c:	20ff      	movs	r0, #255	@ 0xff
 800451e:	7030      	strb	r0, [r6, #0]
 8004520:	1c30      	adds	r0, r6, #0
 8004522:	b001      	add	sp, #4
 8004524:	bc08      	pop	{r3}
 8004526:	4698      	mov	r8, r3
 8004528:	bcf0      	pop	{r4, r5, r6, r7}
 800452a:	bc02      	pop	{r1}
 800452c:	4708      	bx	r1
 800452e:	0000      	movs	r0, r0
 8004530:	b530      	push	{r4, r5, lr}
 8004532:	1c04      	adds	r4, r0, #0
 8004534:	1c0d      	adds	r5, r1, #0
 8004536:	782a      	ldrb	r2, [r5, #0]
 8004538:	3501      	adds	r5, #1
 800453a:	1c10      	adds	r0, r2, #0
 800453c:	38fa      	subs	r0, #250	@ 0xfa
 800453e:	2805      	cmp	r0, #5
 8004540:	d83b      	bhi.n	0x80045ba
 8004542:	0080      	lsls	r0, r0, #2
 8004544:	4901      	ldr	r1, [pc, #4]	@ (0x800454c)
 8004546:	1840      	adds	r0, r0, r1
 8004548:	6800      	ldr	r0, [r0, #0]
 800454a:	4687      	mov	pc, r0
 800454c:	4550      	cmp	r0, sl
 800454e:	0800      	lsrs	r0, r0, #32
 8004550:	45ba      	cmp	sl, r7
 8004552:	0800      	lsrs	r0, r0, #32
 8004554:	45ba      	cmp	sl, r7
 8004556:	0800      	lsrs	r0, r0, #32
 8004558:	457c      	cmp	r4, pc
 800455a:	0800      	lsrs	r0, r0, #32
 800455c:	4568      	cmp	r0, sp
 800455e:	0800      	lsrs	r0, r0, #32
 8004560:	45ba      	cmp	sl, r7
 8004562:	0800      	lsrs	r0, r0, #32
 8004564:	45c0      	cmp	r8, r8
 8004566:	0800      	lsrs	r0, r0, #32
 8004568:	7828      	ldrb	r0, [r5, #0]
 800456a:	3501      	adds	r5, #1
 800456c:	f000 f8b2 	bl	0x80046d4
 8004570:	1c01      	adds	r1, r0, #0
 8004572:	1c20      	adds	r0, r4, #0
 8004574:	f7ff ffdc 	bl	0x8004530
 8004578:	1c04      	adds	r4, r0, #0
 800457a:	e7dc      	b.n	0x8004536
 800457c:	7022      	strb	r2, [r4, #0]
 800457e:	3401      	adds	r4, #1
 8004580:	782a      	ldrb	r2, [r5, #0]
 8004582:	3501      	adds	r5, #1
 8004584:	7022      	strb	r2, [r4, #0]
 8004586:	3401      	adds	r4, #1
 8004588:	2a07      	cmp	r2, #7
 800458a:	d0d4      	beq.n	0x8004536
 800458c:	2a07      	cmp	r2, #7
 800458e:	dc02      	bgt.n	0x8004596
 8004590:	2a04      	cmp	r2, #4
 8004592:	d005      	beq.n	0x80045a0
 8004594:	e00c      	b.n	0x80045b0
 8004596:	2a09      	cmp	r2, #9
 8004598:	d0cd      	beq.n	0x8004536
 800459a:	2a0f      	cmp	r2, #15
 800459c:	d108      	bne.n	0x80045b0
 800459e:	e7ca      	b.n	0x8004536
 80045a0:	7828      	ldrb	r0, [r5, #0]
 80045a2:	7020      	strb	r0, [r4, #0]
 80045a4:	3501      	adds	r5, #1
 80045a6:	3401      	adds	r4, #1
 80045a8:	7828      	ldrb	r0, [r5, #0]
 80045aa:	7020      	strb	r0, [r4, #0]
 80045ac:	3501      	adds	r5, #1
 80045ae:	3401      	adds	r4, #1
 80045b0:	7828      	ldrb	r0, [r5, #0]
 80045b2:	7020      	strb	r0, [r4, #0]
 80045b4:	3501      	adds	r5, #1
 80045b6:	3401      	adds	r4, #1
 80045b8:	e7bd      	b.n	0x8004536
 80045ba:	7022      	strb	r2, [r4, #0]
 80045bc:	3401      	adds	r4, #1
 80045be:	e7ba      	b.n	0x8004536
 80045c0:	20ff      	movs	r0, #255	@ 0xff
 80045c2:	7020      	strb	r0, [r4, #0]
 80045c4:	1c20      	adds	r0, r4, #0
 80045c6:	bc30      	pop	{r4, r5}
 80045c8:	bc02      	pop	{r1}
 80045ca:	4708      	bx	r1
 80045cc:	b570      	push	{r4, r5, r6, lr}
 80045ce:	b083      	sub	sp, #12
 80045d0:	1c05      	adds	r5, r0, #0
 80045d2:	1c0e      	adds	r6, r1, #0
 80045d4:	490b      	ldr	r1, [pc, #44]	@ (0x8004604)
 80045d6:	4668      	mov	r0, sp
 80045d8:	2204      	movs	r2, #4
 80045da:	f1ae fde3 	bl	0x81b31a4
 80045de:	ac01      	add	r4, sp, #4
 80045e0:	4909      	ldr	r1, [pc, #36]	@ (0x8004608)
 80045e2:	1c20      	adds	r0, r4, #0
 80045e4:	2205      	movs	r2, #5
 80045e6:	f1ae fddd 	bl	0x81b31a4
 80045ea:	1c28      	adds	r0, r5, #0
 80045ec:	4669      	mov	r1, sp
 80045ee:	f7ff fe7b 	bl	0x80042e8
 80045f2:	1c05      	adds	r5, r0, #0
 80045f4:	7830      	ldrb	r0, [r6, #0]
 80045f6:	3601      	adds	r6, #1
 80045f8:	28fe      	cmp	r0, #254	@ 0xfe
 80045fa:	d007      	beq.n	0x800460c
 80045fc:	28ff      	cmp	r0, #255	@ 0xff
 80045fe:	d108      	bne.n	0x8004612
 8004600:	e00d      	b.n	0x800461e
 8004602:	0000      	movs	r0, r0
 8004604:	babc      	hlt	0x003c
 8004606:	081b      	lsrs	r3, r3, #32
 8004608:	bac0      	revsh	r0, r0
 800460a:	081b      	lsrs	r3, r3, #32
 800460c:	1c28      	adds	r0, r5, #0
 800460e:	1c21      	adds	r1, r4, #0
 8004610:	e7ed      	b.n	0x80045ee
 8004612:	7028      	strb	r0, [r5, #0]
 8004614:	3501      	adds	r5, #1
 8004616:	3040      	adds	r0, #64	@ 0x40
 8004618:	7028      	strb	r0, [r5, #0]
 800461a:	3501      	adds	r5, #1
 800461c:	e7ea      	b.n	0x80045f4
 800461e:	7028      	strb	r0, [r5, #0]
 8004620:	1c28      	adds	r0, r5, #0
 8004622:	b003      	add	sp, #12
 8004624:	bc70      	pop	{r4, r5, r6}
 8004626:	bc02      	pop	{r1}
 8004628:	4708      	bx	r1
 800462a:	0000      	movs	r0, r0
 800462c:	4800      	ldr	r0, [pc, #0]	@ (0x8004630)
 800462e:	4770      	bx	lr
 8004630:	2870      	cmp	r0, #112	@ 0x70
 8004632:	0300      	lsls	r0, r0, #12
 8004634:	4800      	ldr	r0, [pc, #0]	@ (0x8004638)
 8004636:	4770      	bx	lr
 8004638:	4c04      	ldr	r4, [pc, #16]	@ (0x800464c)
 800463a:	0202      	lsls	r2, r0, #8
 800463c:	4800      	ldr	r0, [pc, #0]	@ (0x8004640)
 800463e:	4770      	bx	lr
 8004640:	31f0      	adds	r1, #240	@ 0xf0
 8004642:	0202      	lsls	r2, r0, #8
 8004644:	4800      	ldr	r0, [pc, #0]	@ (0x8004648)
 8004646:	4770      	bx	lr
 8004648:	3204      	adds	r2, #4
 800464a:	0202      	lsls	r2, r0, #8
 800464c:	4800      	ldr	r0, [pc, #0]	@ (0x8004650)
 800464e:	4770      	bx	lr
 8004650:	3218      	adds	r2, #24
 8004652:	0202      	lsls	r2, r0, #8
 8004654:	b500      	push	{lr}
 8004656:	4803      	ldr	r0, [pc, #12]	@ (0x8004664)
 8004658:	7a00      	ldrb	r0, [r0, #8]
 800465a:	2800      	cmp	r0, #0
 800465c:	d006      	beq.n	0x800466c
 800465e:	4802      	ldr	r0, [pc, #8]	@ (0x8004668)
 8004660:	e005      	b.n	0x800466e
 8004662:	0000      	movs	r0, r0
 8004664:	4c04      	ldr	r4, [pc, #16]	@ (0x8004678)
 8004666:	0202      	lsls	r2, r0, #8
 8004668:	9420      	str	r4, [sp, #128]	@ 0x80
 800466a:	083e      	lsrs	r6, r7, #32
 800466c:	4801      	ldr	r0, [pc, #4]	@ (0x8004674)
 800466e:	bc02      	pop	{r1}
 8004670:	4708      	bx	r1
 8004672:	0000      	movs	r0, r0
 8004674:	941d      	str	r4, [sp, #116]	@ 0x74
 8004676:	083e      	lsrs	r6, r7, #32
 8004678:	b500      	push	{lr}
 800467a:	4803      	ldr	r0, [pc, #12]	@ (0x8004688)
 800467c:	7a00      	ldrb	r0, [r0, #8]
 800467e:	2800      	cmp	r0, #0
 8004680:	d006      	beq.n	0x8004690
 8004682:	4802      	ldr	r0, [pc, #8]	@ (0x800468c)
 8004684:	e005      	b.n	0x8004692
 8004686:	0000      	movs	r0, r0
 8004688:	4c04      	ldr	r4, [pc, #16]	@ (0x800469c)
 800468a:	0202      	lsls	r2, r0, #8
 800468c:	944c      	str	r4, [sp, #304]	@ 0x130
 800468e:	083e      	lsrs	r6, r7, #32
 8004690:	4801      	ldr	r0, [pc, #4]	@ (0x8004698)
 8004692:	bc02      	pop	{r1}
 8004694:	4708      	bx	r1
 8004696:	0000      	movs	r0, r0
 8004698:	9450      	str	r4, [sp, #320]	@ 0x140
 800469a:	083e      	lsrs	r6, r7, #32
 800469c:	4800      	ldr	r0, [pc, #0]	@ (0x80046a0)
 800469e:	4770      	bx	lr
 80046a0:	942a      	str	r4, [sp, #168]	@ 0xa8
 80046a2:	083e      	lsrs	r6, r7, #32
 80046a4:	4800      	ldr	r0, [pc, #0]	@ (0x80046a8)
 80046a6:	4770      	bx	lr
 80046a8:	9432      	str	r4, [sp, #200]	@ 0xc8
 80046aa:	083e      	lsrs	r6, r7, #32
 80046ac:	4800      	ldr	r0, [pc, #0]	@ (0x80046b0)
 80046ae:	4770      	bx	lr
 80046b0:	942e      	str	r4, [sp, #184]	@ 0xb8
 80046b2:	083e      	lsrs	r6, r7, #32
 80046b4:	4800      	ldr	r0, [pc, #0]	@ (0x80046b8)
 80046b6:	4770      	bx	lr
 80046b8:	943b      	str	r4, [sp, #236]	@ 0xec
 80046ba:	083e      	lsrs	r6, r7, #32
 80046bc:	4800      	ldr	r0, [pc, #0]	@ (0x80046c0)
 80046be:	4770      	bx	lr
 80046c0:	9436      	str	r4, [sp, #216]	@ 0xd8
 80046c2:	083e      	lsrs	r6, r7, #32
 80046c4:	4800      	ldr	r0, [pc, #0]	@ (0x80046c8)
 80046c6:	4770      	bx	lr
 80046c8:	9446      	str	r4, [sp, #280]	@ 0x118
 80046ca:	083e      	lsrs	r6, r7, #32
 80046cc:	4800      	ldr	r0, [pc, #0]	@ (0x80046d0)
 80046ce:	4770      	bx	lr
 80046d0:	9440      	str	r4, [sp, #256]	@ 0x100
 80046d2:	083e      	lsrs	r6, r7, #32
 80046d4:	b500      	push	{lr}
 80046d6:	280d      	cmp	r0, #13
 80046d8:	d808      	bhi.n	0x80046ec
 80046da:	4903      	ldr	r1, [pc, #12]	@ (0x80046e8)
 80046dc:	0080      	lsls	r0, r0, #2
 80046de:	1840      	adds	r0, r0, r1
 80046e0:	6800      	ldr	r0, [r0, #0]
 80046e2:	f1ac fdf7 	bl	0x81b12d4
 80046e6:	e002      	b.n	0x80046ee
 80046e8:	bac8      	revsh	r0, r1
 80046ea:	081b      	lsrs	r3, r3, #32
 80046ec:	4801      	ldr	r0, [pc, #4]	@ (0x80046f4)
 80046ee:	bc02      	pop	{r1}
 80046f0:	4708      	bx	r1
 80046f2:	0000      	movs	r0, r0
 80046f4:	941c      	str	r4, [sp, #112]	@ 0x70
 80046f6:	083e      	lsrs	r6, r7, #32
 80046f8:	b500      	push	{lr}
 80046fa:	1c03      	adds	r3, r0, #0
 80046fc:	0609      	lsls	r1, r1, #24
 80046fe:	0e09      	lsrs	r1, r1, #24
 8004700:	0412      	lsls	r2, r2, #16
 8004702:	0c12      	lsrs	r2, r2, #16
 8004704:	2000      	movs	r0, #0
 8004706:	4290      	cmp	r0, r2
 8004708:	d206      	bcs.n	0x8004718
 800470a:	7019      	strb	r1, [r3, #0]
 800470c:	3301      	adds	r3, #1
 800470e:	3001      	adds	r0, #1
 8004710:	0400      	lsls	r0, r0, #16
 8004712:	0c00      	lsrs	r0, r0, #16
 8004714:	4290      	cmp	r0, r2
 8004716:	d3f8      	bcc.n	0x800470a
 8004718:	20ff      	movs	r0, #255	@ 0xff
 800471a:	7018      	strb	r0, [r3, #0]
 800471c:	1c18      	adds	r0, r3, #0
 800471e:	bc02      	pop	{r1}
 8004720:	4708      	bx	r1
 8004722:	0000      	movs	r0, r0
 8004724:	b530      	push	{r4, r5, lr}
 8004726:	1c04      	adds	r4, r0, #0
 8004728:	1c0d      	adds	r5, r1, #0
 800472a:	0612      	lsls	r2, r2, #24
 800472c:	0e12      	lsrs	r2, r2, #24
 800472e:	041b      	lsls	r3, r3, #16
 8004730:	0c1b      	lsrs	r3, r3, #16
 8004732:	e007      	b.n	0x8004744
 8004734:	7021      	strb	r1, [r4, #0]
 8004736:	3501      	adds	r5, #1
 8004738:	3401      	adds	r4, #1
 800473a:	2b00      	cmp	r3, #0
 800473c:	d002      	beq.n	0x8004744
 800473e:	1e58      	subs	r0, r3, #1
 8004740:	0400      	lsls	r0, r0, #16
 8004742:	0c03      	lsrs	r3, r0, #16
 8004744:	7829      	ldrb	r1, [r5, #0]
 8004746:	1c08      	adds	r0, r1, #0
 8004748:	28ff      	cmp	r0, #255	@ 0xff
 800474a:	d1f3      	bne.n	0x8004734
 800474c:	1e58      	subs	r0, r3, #1
 800474e:	0400      	lsls	r0, r0, #16
 8004750:	0c03      	lsrs	r3, r0, #16
 8004752:	4808      	ldr	r0, [pc, #32]	@ (0x8004774)
 8004754:	4283      	cmp	r3, r0
 8004756:	d007      	beq.n	0x8004768
 8004758:	1c01      	adds	r1, r0, #0
 800475a:	7022      	strb	r2, [r4, #0]
 800475c:	3401      	adds	r4, #1
 800475e:	1e58      	subs	r0, r3, #1
 8004760:	0400      	lsls	r0, r0, #16
 8004762:	0c03      	lsrs	r3, r0, #16
 8004764:	428b      	cmp	r3, r1
 8004766:	d1f8      	bne.n	0x800475a
 8004768:	20ff      	movs	r0, #255	@ 0xff
 800476a:	7020      	strb	r0, [r4, #0]
 800476c:	1c20      	adds	r0, r4, #0
 800476e:	bc30      	pop	{r4, r5}
 8004770:	bc02      	pop	{r1}
 8004772:	4708      	bx	r1
 8004774:	ffff 0000 	vaddl.u<illegal width 64>	q8, d15, d0
 8004778:	b500      	push	{lr}
 800477a:	040a      	lsls	r2, r1, #16
 800477c:	0c12      	lsrs	r2, r2, #16
 800477e:	21ff      	movs	r1, #255	@ 0xff
 8004780:	f7ff ffba 	bl	0x80046f8
 8004784:	bc02      	pop	{r1}
 8004786:	4708      	bx	r1
 8004788:	b500      	push	{lr}
 800478a:	0600      	lsls	r0, r0, #24
 800478c:	0e00      	lsrs	r0, r0, #24
 800478e:	f073 fa0f 	bl	0x8077bb0
 8004792:	bc01      	pop	{r0}
 8004794:	4700      	bx	r0
 8004796:	0000      	movs	r0, r0
 8004798:	b5f0      	push	{r4, r5, r6, r7, lr}
 800479a:	4647      	mov	r7, r8
 800479c:	b480      	push	{r7}
 800479e:	1c04      	adds	r4, r0, #0
 80047a0:	0624      	lsls	r4, r4, #24
 80047a2:	0e24      	lsrs	r4, r4, #24
 80047a4:	0609      	lsls	r1, r1, #24
 80047a6:	0e0d      	lsrs	r5, r1, #24
 80047a8:	46a8      	mov	r8, r5
 80047aa:	0612      	lsls	r2, r2, #24
 80047ac:	0e16      	lsrs	r6, r2, #24
 80047ae:	061b      	lsls	r3, r3, #24
 80047b0:	0e1f      	lsrs	r7, r3, #24
 80047b2:	480d      	ldr	r0, [pc, #52]	@ (0x80047e8)
 80047b4:	0121      	lsls	r1, r4, #4
 80047b6:	2220      	movs	r2, #32
 80047b8:	f06c f96a 	bl	0x8070a90
 80047bc:	4a0b      	ldr	r2, [pc, #44]	@ (0x80047ec)
 80047be:	480c      	ldr	r0, [pc, #48]	@ (0x80047f0)
 80047c0:	6010      	str	r0, [r2, #0]
 80047c2:	03b8      	lsls	r0, r7, #14
 80047c4:	21c0      	movs	r1, #192	@ 0xc0
 80047c6:	04c9      	lsls	r1, r1, #19
 80047c8:	1840      	adds	r0, r0, r1
 80047ca:	6050      	str	r0, [r2, #4]
 80047cc:	4809      	ldr	r0, [pc, #36]	@ (0x80047f4)
 80047ce:	6090      	str	r0, [r2, #8]
 80047d0:	6890      	ldr	r0, [r2, #8]
 80047d2:	4809      	ldr	r0, [pc, #36]	@ (0x80047f8)
 80047d4:	6006      	str	r6, [r0, #0]
 80047d6:	6044      	str	r4, [r0, #4]
 80047d8:	2d02      	cmp	r5, #2
 80047da:	d017      	beq.n	0x800480c
 80047dc:	2d02      	cmp	r5, #2
 80047de:	dc0d      	bgt.n	0x80047fc
 80047e0:	2d01      	cmp	r5, #1
 80047e2:	d00f      	beq.n	0x8004804
 80047e4:	e01d      	b.n	0x8004822
 80047e6:	0000      	movs	r0, r0
 80047e8:	bb00      	cbnz	r0, 0x800482c
 80047ea:	081b      	lsrs	r3, r3, #32
 80047ec:	00d4      	lsls	r4, r2, #3
 80047ee:	0400      	lsls	r0, r0, #16
 80047f0:	bb20      	cbnz	r0, 0x800483c
 80047f2:	081b      	lsrs	r3, r3, #32
 80047f4:	0110      	lsls	r0, r2, #4
 80047f6:	8000      	strh	r0, [r0, #0]
 80047f8:	2f20      	cmp	r7, #32
 80047fa:	0300      	lsls	r0, r0, #12
 80047fc:	4640      	mov	r0, r8
 80047fe:	2803      	cmp	r0, #3
 8004800:	d008      	beq.n	0x8004814
 8004802:	e00e      	b.n	0x8004822
 8004804:	4a00      	ldr	r2, [pc, #0]	@ (0x8004808)
 8004806:	e006      	b.n	0x8004816
 8004808:	000a      	movs	r2, r1
 800480a:	0400      	lsls	r0, r0, #16
 800480c:	4a00      	ldr	r2, [pc, #0]	@ (0x8004810)
 800480e:	e002      	b.n	0x8004816
 8004810:	000c      	movs	r4, r1
 8004812:	0400      	lsls	r0, r0, #16
 8004814:	4a05      	ldr	r2, [pc, #20]	@ (0x800482c)
 8004816:	0230      	lsls	r0, r6, #8
 8004818:	2101      	movs	r1, #1
 800481a:	4308      	orrs	r0, r1
 800481c:	00b9      	lsls	r1, r7, #2
 800481e:	4308      	orrs	r0, r1
 8004820:	8010      	strh	r0, [r2, #0]
 8004822:	bc08      	pop	{r3}
 8004824:	4698      	mov	r8, r3
 8004826:	bcf0      	pop	{r4, r5, r6, r7}
 8004828:	bc01      	pop	{r0}
 800482a:	4700      	bx	r0
 800482c:	000e      	movs	r6, r1
 800482e:	0400      	lsls	r0, r0, #16
 8004830:	b570      	push	{r4, r5, r6, lr}
 8004832:	4646      	mov	r6, r8
 8004834:	b440      	push	{r6}
 8004836:	4680      	mov	r8, r0
 8004838:	1c0d      	adds	r5, r1, #0
 800483a:	1c14      	adds	r4, r2, #0
 800483c:	1c1e      	adds	r6, r3, #0
 800483e:	0600      	lsls	r0, r0, #24
 8004840:	0e00      	lsrs	r0, r0, #24
 8004842:	4680      	mov	r8, r0
 8004844:	062d      	lsls	r5, r5, #24
 8004846:	0e2d      	lsrs	r5, r5, #24
 8004848:	0624      	lsls	r4, r4, #24
 800484a:	0e24      	lsrs	r4, r4, #24
 800484c:	0636      	lsls	r6, r6, #24
 800484e:	0e36      	lsrs	r6, r6, #24
 8004850:	4810      	ldr	r0, [pc, #64]	@ (0x8004894)
 8004852:	4642      	mov	r2, r8
 8004854:	0111      	lsls	r1, r2, #4
 8004856:	2220      	movs	r2, #32
 8004858:	f06c f91a 	bl	0x8070a90
 800485c:	4a0e      	ldr	r2, [pc, #56]	@ (0x8004898)
 800485e:	480f      	ldr	r0, [pc, #60]	@ (0x800489c)
 8004860:	6010      	str	r0, [r2, #0]
 8004862:	03b0      	lsls	r0, r6, #14
 8004864:	21c0      	movs	r1, #192	@ 0xc0
 8004866:	04c9      	lsls	r1, r1, #19
 8004868:	1840      	adds	r0, r0, r1
 800486a:	6050      	str	r0, [r2, #4]
 800486c:	480c      	ldr	r0, [pc, #48]	@ (0x80048a0)
 800486e:	6090      	str	r0, [r2, #8]
 8004870:	6890      	ldr	r0, [r2, #8]
 8004872:	480c      	ldr	r0, [pc, #48]	@ (0x80048a4)
 8004874:	6004      	str	r4, [r0, #0]
 8004876:	4641      	mov	r1, r8
 8004878:	6041      	str	r1, [r0, #4]
 800487a:	480b      	ldr	r0, [pc, #44]	@ (0x80048a8)
 800487c:	00ad      	lsls	r5, r5, #2
 800487e:	182d      	adds	r5, r5, r0
 8004880:	6828      	ldr	r0, [r5, #0]
 8004882:	0224      	lsls	r4, r4, #8
 8004884:	00b6      	lsls	r6, r6, #2
 8004886:	4334      	orrs	r4, r6
 8004888:	8004      	strh	r4, [r0, #0]
 800488a:	bc08      	pop	{r3}
 800488c:	4698      	mov	r8, r3
 800488e:	bc70      	pop	{r4, r5, r6}
 8004890:	bc01      	pop	{r0}
 8004892:	4700      	bx	r0
 8004894:	bb00      	cbnz	r0, 0x80048d8
 8004896:	081b      	lsrs	r3, r3, #32
 8004898:	00d4      	lsls	r4, r2, #3
 800489a:	0400      	lsls	r0, r0, #16
 800489c:	bb20      	cbnz	r0, 0x80048e8
 800489e:	081b      	lsrs	r3, r3, #32
 80048a0:	0110      	lsls	r0, r2, #4
 80048a2:	8000      	strh	r0, [r0, #0]
 80048a4:	2f20      	cmp	r7, #32
 80048a6:	0300      	lsls	r0, r0, #12
 80048a8:	343c      	adds	r4, #60	@ 0x3c
 80048aa:	081b      	lsrs	r3, r3, #32
 80048ac:	b570      	push	{r4, r5, r6, lr}
 80048ae:	f7fb ff4d 	bl	0x800074c
 80048b2:	f7fd fd91 	bl	0x80023d8
 80048b6:	f073 f8d5 	bl	0x8077a64
 80048ba:	4824      	ldr	r0, [pc, #144]	@ (0x800494c)
 80048bc:	f7fb fe42 	bl	0x8000544
 80048c0:	2006      	movs	r0, #6
 80048c2:	f7fd ff8b 	bl	0x80027dc
 80048c6:	2006      	movs	r0, #6
 80048c8:	f06a fb56 	bl	0x806ef78
 80048cc:	f000 fd7c 	bl	0x80053c8
 80048d0:	491f      	ldr	r1, [pc, #124]	@ (0x8004950)
 80048d2:	4a20      	ldr	r2, [pc, #128]	@ (0x8004954)
 80048d4:	1c10      	adds	r0, r2, #0
 80048d6:	8008      	strh	r0, [r1, #0]
 80048d8:	f000 f8ce 	bl	0x8004a78
 80048dc:	481e      	ldr	r0, [pc, #120]	@ (0x8004958)
 80048de:	8c00      	ldrh	r0, [r0, #32]
 80048e0:	f039 fc36 	bl	0x803e150
 80048e4:	2400      	movs	r4, #0
 80048e6:	4e1d      	ldr	r6, [pc, #116]	@ (0x800495c)
 80048e8:	25ff      	movs	r5, #255	@ 0xff
 80048ea:	f039 fc21 	bl	0x803e130
 80048ee:	19a1      	adds	r1, r4, r6
 80048f0:	0400      	lsls	r0, r0, #16
 80048f2:	0c00      	lsrs	r0, r0, #16
 80048f4:	4028      	ands	r0, r5
 80048f6:	7008      	strb	r0, [r1, #0]
 80048f8:	3401      	adds	r4, #1
 80048fa:	2c03      	cmp	r4, #3
 80048fc:	ddf5      	ble.n	0x80048ea
 80048fe:	2000      	movs	r0, #0
 8004900:	2102      	movs	r1, #2
 8004902:	2204      	movs	r2, #4
 8004904:	2300      	movs	r3, #0
 8004906:	f7ff ff47 	bl	0x8004798
 800490a:	2180      	movs	r1, #128	@ 0x80
 800490c:	04c9      	lsls	r1, r1, #19
 800490e:	22aa      	movs	r2, #170	@ 0xaa
 8004910:	0152      	lsls	r2, r2, #5
 8004912:	1c10      	adds	r0, r2, #0
 8004914:	8008      	strh	r0, [r1, #0]
 8004916:	4812      	ldr	r0, [pc, #72]	@ (0x8004960)
 8004918:	2100      	movs	r1, #0
 800491a:	f073 f8d3 	bl	0x8077ac4
 800491e:	f073 f97f 	bl	0x8077c20
 8004922:	f7fb ff39 	bl	0x8000798
 8004926:	f7fb ff5d 	bl	0x80007e4
 800492a:	f06c f923 	bl	0x8070b74
 800492e:	490d      	ldr	r1, [pc, #52]	@ (0x8004964)
 8004930:	2000      	movs	r0, #0
 8004932:	6008      	str	r0, [r1, #0]
 8004934:	f000 f824 	bl	0x8004980
 8004938:	480b      	ldr	r0, [pc, #44]	@ (0x8004968)
 800493a:	2100      	movs	r1, #0
 800493c:	f073 f8c2 	bl	0x8077ac4
 8004940:	480a      	ldr	r0, [pc, #40]	@ (0x800496c)
 8004942:	f7fb fd47 	bl	0x80003d4
 8004946:	bc70      	pop	{r4, r5, r6}
 8004948:	bc01      	pop	{r0}
 800494a:	4700      	bx	r0
 800494c:	4a01      	ldr	r2, [pc, #4]	@ (0x8004954)
 800494e:	0800      	lsrs	r0, r0, #32
 8004950:	2ae4      	cmp	r2, #228	@ 0xe4
 8004952:	0300      	lsls	r0, r0, #12
 8004954:	1111      	asrs	r1, r2, #4
 8004956:	0000      	movs	r0, r0
 8004958:	16e0      	asrs	r0, r4, #27
 800495a:	0300      	lsls	r0, r0, #12
 800495c:	4c0e      	ldr	r4, [pc, #56]	@ (0x8004998)
 800495e:	0202      	lsls	r2, r0, #8
 8004960:	4789      			@ <UNDEFINED> instruction: 0x4789
 8004962:	0800      	lsrs	r0, r0, #32
 8004964:	03ac      	lsls	r4, r5, #14
 8004966:	0300      	lsls	r0, r0, #12
 8004968:	5735      	ldrsb	r5, [r6, r4]
 800496a:	0800      	lsrs	r0, r0, #32
 800496c:	4cc1      	ldr	r4, [pc, #772]	@ (0x8004c74)
 800496e:	0800      	lsrs	r0, r0, #32
 8004970:	0600      	lsls	r0, r0, #24
 8004972:	0e00      	lsrs	r0, r0, #24
 8004974:	4901      	ldr	r1, [pc, #4]	@ (0x800497c)
 8004976:	8308      	strh	r0, [r1, #24]
 8004978:	4770      	bx	lr
 800497a:	0000      	movs	r0, r0
 800497c:	2970      	cmp	r1, #112	@ 0x70
 800497e:	0300      	lsls	r0, r0, #12
 8004980:	b5f0      	push	{r4, r5, r6, r7, lr}
 8004982:	4647      	mov	r7, r8
 8004984:	b480      	push	{r7}
 8004986:	4b19      	ldr	r3, [pc, #100]	@ (0x80049ec)
 8004988:	4a19      	ldr	r2, [pc, #100]	@ (0x80049f0)
 800498a:	7a91      	ldrb	r1, [r2, #10]
 800498c:	7ad0      	ldrb	r0, [r2, #11]
 800498e:	0200      	lsls	r0, r0, #8
 8004990:	4301      	orrs	r1, r0
 8004992:	7b10      	ldrb	r0, [r2, #12]
 8004994:	0400      	lsls	r0, r0, #16
 8004996:	4301      	orrs	r1, r0
 8004998:	7b50      	ldrb	r0, [r2, #13]
 800499a:	0600      	lsls	r0, r0, #24
 800499c:	4301      	orrs	r1, r0
 800499e:	6059      	str	r1, [r3, #4]
 80049a0:	2400      	movs	r4, #0
 80049a2:	1c16      	adds	r6, r2, #0
 80049a4:	4f13      	ldr	r7, [pc, #76]	@ (0x80049f4)
 80049a6:	4814      	ldr	r0, [pc, #80]	@ (0x80049f8)
 80049a8:	4684      	mov	ip, r0
 80049aa:	4914      	ldr	r1, [pc, #80]	@ (0x80049fc)
 80049ac:	4688      	mov	r8, r1
 80049ae:	1c1d      	adds	r5, r3, #0
 80049b0:	3508      	adds	r5, #8
 80049b2:	1960      	adds	r0, r4, r5
 80049b4:	18a1      	adds	r1, r4, r2
 80049b6:	7809      	ldrb	r1, [r1, #0]
 80049b8:	7001      	strb	r1, [r0, #0]
 80049ba:	3401      	adds	r4, #1
 80049bc:	2c0a      	cmp	r4, #10
 80049be:	ddf8      	ble.n	0x80049b2
 80049c0:	7a30      	ldrb	r0, [r6, #8]
 80049c2:	2200      	movs	r2, #0
 80049c4:	74d8      	strb	r0, [r3, #19]
 80049c6:	8838      	ldrh	r0, [r7, #0]
 80049c8:	6158      	str	r0, [r3, #20]
 80049ca:	4664      	mov	r4, ip
 80049cc:	7820      	ldrb	r0, [r4, #0]
 80049ce:	8358      	strh	r0, [r3, #26]
 80049d0:	4641      	mov	r1, r8
 80049d2:	7808      	ldrb	r0, [r1, #0]
 80049d4:	2480      	movs	r4, #128	@ 0x80
 80049d6:	01e4      	lsls	r4, r4, #7
 80049d8:	1c21      	adds	r1, r4, #0
 80049da:	1840      	adds	r0, r0, r1
 80049dc:	8018      	strh	r0, [r3, #0]
 80049de:	805a      	strh	r2, [r3, #2]
 80049e0:	bc08      	pop	{r3}
 80049e2:	4698      	mov	r8, r3
 80049e4:	bcf0      	pop	{r4, r5, r6, r7}
 80049e6:	bc01      	pop	{r0}
 80049e8:	4700      	bx	r0
 80049ea:	0000      	movs	r0, r0
 80049ec:	2970      	cmp	r1, #112	@ 0x70
 80049ee:	0300      	lsls	r0, r0, #12
 80049f0:	4c04      	ldr	r4, [pc, #16]	@ (0x8004a04)
 80049f2:	0202      	lsls	r2, r0, #8
 80049f4:	2ae4      	cmp	r2, #228	@ 0xe4
 80049f6:	0300      	lsls	r0, r0, #12
 80049f8:	32b5      	adds	r2, #181	@ 0xb5
 80049fa:	081b      	lsrs	r3, r3, #32
 80049fc:	32b4      	adds	r2, #180	@ 0xb4
 80049fe:	081b      	lsrs	r3, r3, #32
 8004a00:	b500      	push	{lr}
 8004a02:	f7fc faad 	bl	0x8000f60
 8004a06:	f7fc fbfd 	bl	0x8001204
 8004a0a:	f06c f885 	bl	0x8070b18
 8004a0e:	bc01      	pop	{r0}
 8004a10:	4700      	bx	r0
 8004a12:	0000      	movs	r0, r0
 8004a14:	b500      	push	{lr}
 8004a16:	4b07      	ldr	r3, [pc, #28]	@ (0x8004a34)
 8004a18:	4907      	ldr	r1, [pc, #28]	@ (0x8004a38)
 8004a1a:	4a08      	ldr	r2, [pc, #32]	@ (0x8004a3c)
 8004a1c:	1c08      	adds	r0, r1, #0
 8004a1e:	300e      	adds	r0, #14
 8004a20:	8002      	strh	r2, [r0, #0]
 8004a22:	3802      	subs	r0, #2
 8004a24:	4288      	cmp	r0, r1
 8004a26:	dafb      	bge.n	0x8004a20
 8004a28:	2001      	movs	r0, #1
 8004a2a:	7018      	strb	r0, [r3, #0]
 8004a2c:	f001 f9ac 	bl	0x8005d88
 8004a30:	bc01      	pop	{r0}
 8004a32:	4700      	bx	r0
 8004a34:	3620      	adds	r6, #32
 8004a36:	0202      	lsls	r2, r0, #8
 8004a38:	2f00      	cmp	r7, #0
 8004a3a:	0300      	lsls	r0, r0, #12
 8004a3c:	efff 0000 	vext.8	d16, d15, d0, #0
 8004a40:	b500      	push	{lr}
 8004a42:	0600      	lsls	r0, r0, #24
 8004a44:	0e02      	lsrs	r2, r0, #24
 8004a46:	480a      	ldr	r0, [pc, #40]	@ (0x8004a70)
 8004a48:	0091      	lsls	r1, r2, #2
 8004a4a:	1889      	adds	r1, r1, r2
 8004a4c:	00c9      	lsls	r1, r1, #3
 8004a4e:	1809      	adds	r1, r1, r0
 8004a50:	8908      	ldrh	r0, [r1, #8]
 8004a52:	3001      	adds	r0, #1
 8004a54:	8108      	strh	r0, [r1, #8]
 8004a56:	0400      	lsls	r0, r0, #16
 8004a58:	1400      	asrs	r0, r0, #16
 8004a5a:	2805      	cmp	r0, #5
 8004a5c:	d105      	bne.n	0x8004a6a
 8004a5e:	4905      	ldr	r1, [pc, #20]	@ (0x8004a74)
 8004a60:	2001      	movs	r0, #1
 8004a62:	7008      	strb	r0, [r1, #0]
 8004a64:	1c10      	adds	r0, r2, #0
 8004a66:	f073 f8a3 	bl	0x8077bb0
 8004a6a:	bc01      	pop	{r0}
 8004a6c:	4700      	bx	r0
 8004a6e:	0000      	movs	r0, r0
 8004a70:	4a50      	ldr	r2, [pc, #320]	@ (0x8004bb4)
 8004a72:	0300      	lsls	r0, r0, #12
 8004a74:	2fb0      	cmp	r7, #176	@ 0xb0
 8004a76:	0300      	lsls	r0, r0, #12
 8004a78:	b530      	push	{r4, r5, lr}
 8004a7a:	f001 f9e3 	bl	0x8005e44
 8004a7e:	f7ff ffc9 	bl	0x8004a14
 8004a82:	4913      	ldr	r1, [pc, #76]	@ (0x8004ad0)
 8004a84:	4813      	ldr	r0, [pc, #76]	@ (0x8004ad4)
 8004a86:	6008      	str	r0, [r1, #0]
 8004a88:	4813      	ldr	r0, [pc, #76]	@ (0x8004ad8)
 8004a8a:	2100      	movs	r1, #0
 8004a8c:	7001      	strb	r1, [r0, #0]
 8004a8e:	4813      	ldr	r0, [pc, #76]	@ (0x8004adc)
 8004a90:	7001      	strb	r1, [r0, #0]
 8004a92:	4813      	ldr	r0, [pc, #76]	@ (0x8004ae0)
 8004a94:	7001      	strb	r1, [r0, #0]
 8004a96:	f000 fdad 	bl	0x80055f4
 8004a9a:	4812      	ldr	r0, [pc, #72]	@ (0x8004ae4)
 8004a9c:	2100      	movs	r1, #0
 8004a9e:	6001      	str	r1, [r0, #0]
 8004aa0:	4811      	ldr	r0, [pc, #68]	@ (0x8004ae8)
 8004aa2:	7001      	strb	r1, [r0, #0]
 8004aa4:	4811      	ldr	r0, [pc, #68]	@ (0x8004aec)
 8004aa6:	7001      	strb	r1, [r0, #0]
 8004aa8:	4811      	ldr	r0, [pc, #68]	@ (0x8004af0)
 8004aaa:	7001      	strb	r1, [r0, #0]
 8004aac:	4d11      	ldr	r5, [pc, #68]	@ (0x8004af4)
 8004aae:	2400      	movs	r4, #0
 8004ab0:	2301      	movs	r3, #1
 8004ab2:	4a11      	ldr	r2, [pc, #68]	@ (0x8004af8)
 8004ab4:	1948      	adds	r0, r1, r5
 8004ab6:	7003      	strb	r3, [r0, #0]
 8004ab8:	1888      	adds	r0, r1, r2
 8004aba:	7004      	strb	r4, [r0, #0]
 8004abc:	3101      	adds	r1, #1
 8004abe:	2903      	cmp	r1, #3
 8004ac0:	ddf8      	ble.n	0x8004ab4
 8004ac2:	480e      	ldr	r0, [pc, #56]	@ (0x8004afc)
 8004ac4:	2102      	movs	r1, #2
 8004ac6:	f072 fffd 	bl	0x8077ac4
 8004aca:	bc30      	pop	{r4, r5}
 8004acc:	bc01      	pop	{r0}
 8004ace:	4700      	bx	r0
 8004ad0:	2f30      	cmp	r7, #48	@ 0x30
 8004ad2:	0300      	lsls	r0, r0, #12
 8004ad4:	5709      	ldrsb	r1, [r1, r4]
 8004ad6:	0800      	lsrs	r0, r0, #32
 8004ad8:	1b68      	subs	r0, r5, r5
 8004ada:	0300      	lsls	r0, r0, #12
 8004adc:	28cc      	cmp	r0, #204	@ 0xcc
 8004ade:	0300      	lsls	r0, r0, #12
 8004ae0:	2ef0      	cmp	r6, #240	@ 0xf0
 8004ae2:	0300      	lsls	r0, r0, #12
 8004ae4:	0394      	lsls	r4, r2, #14
 8004ae6:	0300      	lsls	r0, r0, #12
 8004ae8:	29d8      	cmp	r1, #216	@ 0xd8
 8004aea:	0300      	lsls	r0, r0, #12
 8004aec:	29d4      	cmp	r1, #212	@ 0xd4
 8004aee:	0300      	lsls	r0, r0, #12
 8004af0:	2f14      	cmp	r7, #20
 8004af2:	0300      	lsls	r0, r0, #12
 8004af4:	28dc      	cmp	r0, #220	@ 0xdc
 8004af6:	0300      	lsls	r0, r0, #12
 8004af8:	2ae8      	cmp	r2, #232	@ 0xe8
 8004afa:	0300      	lsls	r0, r0, #12
 8004afc:	4a41      	ldr	r2, [pc, #260]	@ (0x8004c04)
 8004afe:	0800      	lsrs	r0, r0, #32
 8004b00:	b500      	push	{lr}
 8004b02:	4804      	ldr	r0, [pc, #16]	@ (0x8004b14)
 8004b04:	2100      	movs	r1, #0
 8004b06:	7001      	strb	r1, [r0, #0]
 8004b08:	4803      	ldr	r0, [pc, #12]	@ (0x8004b18)
 8004b0a:	7001      	strb	r1, [r0, #0]
 8004b0c:	f001 f90c 	bl	0x8005d28
 8004b10:	bc01      	pop	{r0}
 8004b12:	4700      	bx	r0
 8004b14:	2f14      	cmp	r7, #20
 8004b16:	0300      	lsls	r0, r0, #12
 8004b18:	3620      	adds	r6, #32
 8004b1a:	0202      	lsls	r2, r0, #8
 8004b1c:	b5f0      	push	{r4, r5, r6, r7, lr}
 8004b1e:	464f      	mov	r7, r9
 8004b20:	4646      	mov	r6, r8
 8004b22:	b4c0      	push	{r6, r7}
 8004b24:	4d2e      	ldr	r5, [pc, #184]	@ (0x8004be0)
 8004b26:	4c2f      	ldr	r4, [pc, #188]	@ (0x8004be4)
 8004b28:	7828      	ldrb	r0, [r5, #0]
 8004b2a:	8821      	ldrh	r1, [r4, #0]
 8004b2c:	4288      	cmp	r0, r1
 8004b2e:	d007      	beq.n	0x8004b40
 8004b30:	8820      	ldrh	r0, [r4, #0]
 8004b32:	2102      	movs	r1, #2
 8004b34:	2203      	movs	r2, #3
 8004b36:	2302      	movs	r3, #2
 8004b38:	f000 fdbc 	bl	0x80056b4
 8004b3c:	8820      	ldrh	r0, [r4, #0]
 8004b3e:	7028      	strb	r0, [r5, #0]
 8004b40:	2500      	movs	r5, #0
 8004b42:	4f29      	ldr	r7, [pc, #164]	@ (0x8004be8)
 8004b44:	4829      	ldr	r0, [pc, #164]	@ (0x8004bec)
 8004b46:	182e      	adds	r6, r5, r0
 8004b48:	0068      	lsls	r0, r5, #1
 8004b4a:	1940      	adds	r0, r0, r5
 8004b4c:	0080      	lsls	r0, r0, #2
 8004b4e:	19c4      	adds	r4, r0, r7
 8004b50:	7830      	ldrb	r0, [r6, #0]
 8004b52:	8821      	ldrh	r1, [r4, #0]
 8004b54:	4288      	cmp	r0, r1
 8004b56:	d009      	beq.n	0x8004b6c
 8004b58:	8820      	ldrh	r0, [r4, #0]
 8004b5a:	1d2a      	adds	r2, r5, #4
 8004b5c:	0612      	lsls	r2, r2, #24
 8004b5e:	0e12      	lsrs	r2, r2, #24
 8004b60:	2102      	movs	r1, #2
 8004b62:	2302      	movs	r3, #2
 8004b64:	f000 fda6 	bl	0x80056b4
 8004b68:	8820      	ldrh	r0, [r4, #0]
 8004b6a:	7030      	strb	r0, [r6, #0]
 8004b6c:	1c68      	adds	r0, r5, #1
 8004b6e:	0600      	lsls	r0, r0, #24
 8004b70:	0e05      	lsrs	r5, r0, #24
 8004b72:	2d03      	cmp	r5, #3
 8004b74:	d9e6      	bls.n	0x8004b44
 8004b76:	f000 fd23 	bl	0x80055c0
 8004b7a:	0600      	lsls	r0, r0, #24
 8004b7c:	0e07      	lsrs	r7, r0, #24
 8004b7e:	2f0f      	cmp	r7, #15
 8004b80:	d127      	bne.n	0x8004bd2
 8004b82:	2500      	movs	r5, #0
 8004b84:	4818      	ldr	r0, [pc, #96]	@ (0x8004be8)
 8004b86:	4681      	mov	r9, r0
 8004b88:	4919      	ldr	r1, [pc, #100]	@ (0x8004bf0)
 8004b8a:	4688      	mov	r8, r1
 8004b8c:	1c38      	adds	r0, r7, #0
 8004b8e:	4128      	asrs	r0, r5
 8004b90:	2101      	movs	r1, #1
 8004b92:	4008      	ands	r0, r1
 8004b94:	2800      	cmp	r0, #0
 8004b96:	d017      	beq.n	0x8004bc8
 8004b98:	0228      	lsls	r0, r5, #8
 8004b9a:	4916      	ldr	r1, [pc, #88]	@ (0x8004bf4)
 8004b9c:	1840      	adds	r0, r0, r1
 8004b9e:	006c      	lsls	r4, r5, #1
 8004ba0:	1961      	adds	r1, r4, r5
 8004ba2:	0089      	lsls	r1, r1, #2
 8004ba4:	4449      	add	r1, r9
 8004ba6:	8849      	ldrh	r1, [r1, #2]
 8004ba8:	f000 fd52 	bl	0x8005650
 8004bac:	4912      	ldr	r1, [pc, #72]	@ (0x8004bf8)
 8004bae:	1864      	adds	r4, r4, r1
 8004bb0:	2600      	movs	r6, #0
 8004bb2:	8020      	strh	r0, [r4, #0]
 8004bb4:	1c28      	adds	r0, r5, #0
 8004bb6:	f000 fd29 	bl	0x800560c
 8004bba:	8820      	ldrh	r0, [r4, #0]
 8004bbc:	4540      	cmp	r0, r8
 8004bbe:	d003      	beq.n	0x8004bc8
 8004bc0:	480e      	ldr	r0, [pc, #56]	@ (0x8004bfc)
 8004bc2:	7006      	strb	r6, [r0, #0]
 8004bc4:	480e      	ldr	r0, [pc, #56]	@ (0x8004c00)
 8004bc6:	7006      	strb	r6, [r0, #0]
 8004bc8:	1c68      	adds	r0, r5, #1
 8004bca:	0600      	lsls	r0, r0, #24
 8004bcc:	0e05      	lsrs	r5, r0, #24
 8004bce:	2d03      	cmp	r5, #3
 8004bd0:	d9dc      	bls.n	0x8004b8c
 8004bd2:	bc18      	pop	{r3, r4}
 8004bd4:	4698      	mov	r8, r3
 8004bd6:	46a1      	mov	r9, r4
 8004bd8:	bcf0      	pop	{r4, r5, r6, r7}
 8004bda:	bc01      	pop	{r0}
 8004bdc:	4700      	bx	r0
 8004bde:	0000      	movs	r0, r0
 8004be0:	03b0      	lsls	r0, r6, #14
 8004be2:	0300      	lsls	r0, r0, #12
 8004be4:	0350      	lsls	r0, r2, #13
 8004be6:	0300      	lsls	r0, r0, #12
 8004be8:	0360      	lsls	r0, r4, #13
 8004bea:	0300      	lsls	r0, r0, #12
 8004bec:	03b4      	lsls	r4, r6, #14
 8004bee:	0300      	lsls	r0, r0, #12
 8004bf0:	0342      	lsls	r2, r0, #13
 8004bf2:	0000      	movs	r0, r0
 8004bf4:	2af0      	cmp	r2, #240	@ 0xf0
 8004bf6:	0300      	lsls	r0, r0, #12
 8004bf8:	2fb8      	cmp	r7, #184	@ 0xb8
 8004bfa:	0300      	lsls	r0, r0, #12
 8004bfc:	3614      	adds	r6, #20
 8004bfe:	0202      	lsls	r2, r0, #8
 8004c00:	3615      	adds	r6, #21
 8004c02:	0202      	lsls	r2, r0, #8
 8004c04:	b530      	push	{r4, r5, lr}
 8004c06:	b081      	sub	sp, #4
 8004c08:	4c26      	ldr	r4, [pc, #152]	@ (0x8004ca4)
 8004c0a:	8de1      	ldrh	r1, [r4, #46]	@ 0x2e
 8004c0c:	2001      	movs	r0, #1
 8004c0e:	4008      	ands	r0, r1
 8004c10:	2800      	cmp	r0, #0
 8004c12:	d002      	beq.n	0x8004c1a
 8004c14:	4924      	ldr	r1, [pc, #144]	@ (0x8004ca8)
 8004c16:	2001      	movs	r0, #1
 8004c18:	7008      	strb	r0, [r1, #0]
 8004c1a:	8da1      	ldrh	r1, [r4, #44]	@ 0x2c
 8004c1c:	2502      	movs	r5, #2
 8004c1e:	1c28      	adds	r0, r5, #0
 8004c20:	4008      	ands	r0, r1
 8004c22:	2800      	cmp	r0, #0
 8004c24:	d003      	beq.n	0x8004c2e
 8004c26:	4821      	ldr	r0, [pc, #132]	@ (0x8004cac)
 8004c28:	4921      	ldr	r1, [pc, #132]	@ (0x8004cb0)
 8004c2a:	f000 fbd7 	bl	0x80053dc
 8004c2e:	8de1      	ldrh	r1, [r4, #46]	@ 0x2e
 8004c30:	2080      	movs	r0, #128	@ 0x80
 8004c32:	0080      	lsls	r0, r0, #2
 8004c34:	4008      	ands	r0, r1
 8004c36:	2800      	cmp	r0, #0
 8004c38:	d007      	beq.n	0x8004c4a
 8004c3a:	2001      	movs	r0, #1
 8004c3c:	4240      	negs	r0, r0
 8004c3e:	9500      	str	r5, [sp, #0]
 8004c40:	2100      	movs	r1, #0
 8004c42:	2210      	movs	r2, #16
 8004c44:	2300      	movs	r3, #0
 8004c46:	f06b fff1 	bl	0x8070c2c
 8004c4a:	8de1      	ldrh	r1, [r4, #46]	@ 0x2e
 8004c4c:	2008      	movs	r0, #8
 8004c4e:	4008      	ands	r0, r1
 8004c50:	2800      	cmp	r0, #0
 8004c52:	d002      	beq.n	0x8004c5a
 8004c54:	2001      	movs	r0, #1
 8004c56:	f001 f85b 	bl	0x8005d10
 8004c5a:	8de1      	ldrh	r1, [r4, #46]	@ 0x2e
 8004c5c:	2080      	movs	r0, #128	@ 0x80
 8004c5e:	0040      	lsls	r0, r0, #1
 8004c60:	4008      	ands	r0, r1
 8004c62:	2800      	cmp	r0, #0
 8004c64:	d002      	beq.n	0x8004c6c
 8004c66:	2001      	movs	r0, #1
 8004c68:	f11b ff8a 	bl	0x8120b80
 8004c6c:	8de1      	ldrh	r1, [r4, #46]	@ 0x2e
 8004c6e:	2004      	movs	r0, #4
 8004c70:	4008      	ands	r0, r1
 8004c72:	2800      	cmp	r0, #0
 8004c74:	d001      	beq.n	0x8004c7a
 8004c76:	f000 fec7 	bl	0x8005a08
 8004c7a:	480e      	ldr	r0, [pc, #56]	@ (0x8004cb4)
 8004c7c:	7800      	ldrb	r0, [r0, #0]
 8004c7e:	2800      	cmp	r0, #0
 8004c80:	d00b      	beq.n	0x8004c9a
 8004c82:	6a22      	ldr	r2, [r4, #32]
 8004c84:	480c      	ldr	r0, [pc, #48]	@ (0x8004cb8)
 8004c86:	7801      	ldrb	r1, [r0, #0]
 8004c88:	480c      	ldr	r0, [pc, #48]	@ (0x8004cbc)
 8004c8a:	6800      	ldr	r0, [r0, #0]
 8004c8c:	2800      	cmp	r0, #0
 8004c8e:	d101      	bne.n	0x8004c94
 8004c90:	2010      	movs	r0, #16
 8004c92:	4301      	orrs	r1, r0
 8004c94:	1c10      	adds	r0, r2, #0
 8004c96:	f000 fde3 	bl	0x8005860
 8004c9a:	b001      	add	sp, #4
 8004c9c:	bc30      	pop	{r4, r5}
 8004c9e:	bc01      	pop	{r0}
 8004ca0:	4700      	bx	r0
 8004ca2:	0000      	movs	r0, r0
 8004ca4:	16e0      	asrs	r0, r4, #27
 8004ca6:	0300      	lsls	r0, r0, #12
 8004ca8:	2fb0      	cmp	r7, #176	@ 0xb0
 8004caa:	0300      	lsls	r0, r0, #12
 8004cac:	4000      	ands	r0, r0
 8004cae:	0200      	lsls	r0, r0, #8
 8004cb0:	2004      	movs	r0, #4
 8004cb2:	0000      	movs	r0, r0
 8004cb4:	3614      	adds	r6, #20
 8004cb6:	0202      	lsls	r2, r0, #8
 8004cb8:	1b68      	subs	r0, r5, r5
 8004cba:	0300      	lsls	r0, r0, #12
 8004cbc:	2f30      	cmp	r7, #48	@ 0x30
 8004cbe:	0300      	lsls	r0, r0, #12
 8004cc0:	b500      	push	{lr}
 8004cc2:	f7ff ff9f 	bl	0x8004c04
 8004cc6:	2001      	movs	r0, #1
 8004cc8:	2101      	movs	r1, #1
 8004cca:	2200      	movs	r2, #0
 8004ccc:	f7ff ff26 	bl	0x8004b1c
 8004cd0:	f072 ffa6 	bl	0x8077c20
 8004cd4:	f7fb fd60 	bl	0x8000798
 8004cd8:	f7fb fd84 	bl	0x80007e4
 8004cdc:	f06b ff4a 	bl	0x8070b74
 8004ce0:	bc01      	pop	{r0}
 8004ce2:	4700      	bx	r0
 8004ce4:	b530      	push	{r4, r5, lr}
 8004ce6:	1c04      	adds	r4, r0, #0
 8004ce8:	4802      	ldr	r0, [pc, #8]	@ (0x8004cf4)
 8004cea:	7800      	ldrb	r0, [r0, #0]
 8004cec:	2800      	cmp	r0, #0
 8004cee:	d103      	bne.n	0x8004cf8
 8004cf0:	2000      	movs	r0, #0
 8004cf2:	e025      	b.n	0x8004d40
 8004cf4:	3620      	adds	r6, #32
 8004cf6:	0202      	lsls	r2, r0, #8
 8004cf8:	2100      	movs	r1, #0
 8004cfa:	4d13      	ldr	r5, [pc, #76]	@ (0x8004d48)
 8004cfc:	4b13      	ldr	r3, [pc, #76]	@ (0x8004d4c)
 8004cfe:	2200      	movs	r2, #0
 8004d00:	0048      	lsls	r0, r1, #1
 8004d02:	18c0      	adds	r0, r0, r3
 8004d04:	8002      	strh	r2, [r0, #0]
 8004d06:	1c48      	adds	r0, r1, #1
 8004d08:	0600      	lsls	r0, r0, #24
 8004d0a:	0e01      	lsrs	r1, r0, #24
 8004d0c:	2907      	cmp	r1, #7
 8004d0e:	d9f7      	bls.n	0x8004d00
 8004d10:	8820      	ldrh	r0, [r4, #0]
 8004d12:	8028      	strh	r0, [r5, #0]
 8004d14:	480e      	ldr	r0, [pc, #56]	@ (0x8004d50)
 8004d16:	6800      	ldr	r0, [r0, #0]
 8004d18:	2140      	movs	r1, #64	@ 0x40
 8004d1a:	4008      	ands	r0, r1
 8004d1c:	2800      	cmp	r0, #0
 8004d1e:	d00d      	beq.n	0x8004d3c
 8004d20:	480c      	ldr	r0, [pc, #48]	@ (0x8004d54)
 8004d22:	6800      	ldr	r0, [r0, #0]
 8004d24:	0680      	lsls	r0, r0, #26
 8004d26:	0f80      	lsrs	r0, r0, #30
 8004d28:	f000 f83c 	bl	0x8004da4
 8004d2c:	480a      	ldr	r0, [pc, #40]	@ (0x8004d58)
 8004d2e:	6800      	ldr	r0, [r0, #0]
 8004d30:	2800      	cmp	r0, #0
 8004d32:	d001      	beq.n	0x8004d38
 8004d34:	f1ac face 	bl	0x81b12d4
 8004d38:	f000 ff14 	bl	0x8005b64
 8004d3c:	4804      	ldr	r0, [pc, #16]	@ (0x8004d50)
 8004d3e:	8800      	ldrh	r0, [r0, #0]
 8004d40:	bc30      	pop	{r4, r5}
 8004d42:	bc02      	pop	{r1}
 8004d44:	4708      	bx	r1
 8004d46:	0000      	movs	r0, r0
 8004d48:	2958      	cmp	r1, #88	@ 0x58
 8004d4a:	0300      	lsls	r0, r0, #12
 8004d4c:	2f00      	cmp	r7, #0
 8004d4e:	0300      	lsls	r0, r0, #12
 8004d50:	29d0      	cmp	r1, #208	@ 0xd0
 8004d52:	0300      	lsls	r0, r0, #12
 8004d54:	0128      	lsls	r0, r5, #4
 8004d56:	0400      	lsls	r0, r0, #16
 8004d58:	2f30      	cmp	r7, #48	@ 0x30
 8004d5a:	0300      	lsls	r0, r0, #12
 8004d5c:	b570      	push	{r4, r5, r6, lr}
 8004d5e:	0600      	lsls	r0, r0, #24
 8004d60:	0e00      	lsrs	r0, r0, #24
 8004d62:	2500      	movs	r5, #0
 8004d64:	4902      	ldr	r1, [pc, #8]	@ (0x8004d70)
 8004d66:	1840      	adds	r0, r0, r1
 8004d68:	7005      	strb	r5, [r0, #0]
 8004d6a:	2400      	movs	r4, #0
 8004d6c:	1c0e      	adds	r6, r1, #0
 8004d6e:	e005      	b.n	0x8004d7c
 8004d70:	28dc      	cmp	r0, #220	@ 0xdc
 8004d72:	0300      	lsls	r0, r0, #12
 8004d74:	19a0      	adds	r0, r4, r6
 8004d76:	7800      	ldrb	r0, [r0, #0]
 8004d78:	182d      	adds	r5, r5, r0
 8004d7a:	3401      	adds	r4, #1
 8004d7c:	f000 fe2e 	bl	0x80059dc
 8004d80:	0600      	lsls	r0, r0, #24
 8004d82:	0e00      	lsrs	r0, r0, #24
 8004d84:	4284      	cmp	r4, r0
 8004d86:	dbf5      	blt.n	0x8004d74
 8004d88:	2d00      	cmp	r5, #0
 8004d8a:	d105      	bne.n	0x8004d98
 8004d8c:	4904      	ldr	r1, [pc, #16]	@ (0x8004da0)
 8004d8e:	7808      	ldrb	r0, [r1, #0]
 8004d90:	2800      	cmp	r0, #0
 8004d92:	d101      	bne.n	0x8004d98
 8004d94:	2001      	movs	r0, #1
 8004d96:	7008      	strb	r0, [r1, #0]
 8004d98:	bc70      	pop	{r4, r5, r6}
 8004d9a:	bc01      	pop	{r0}
 8004d9c:	4700      	bx	r0
 8004d9e:	0000      	movs	r0, r0
 8004da0:	2f14      	cmp	r7, #20
 8004da2:	0300      	lsls	r0, r0, #12
 8004da4:	b5f0      	push	{r4, r5, r6, r7, lr}
 8004da6:	4657      	mov	r7, sl
 8004da8:	464e      	mov	r6, r9
 8004daa:	4645      	mov	r5, r8
 8004dac:	b4e0      	push	{r5, r6, r7}
 8004dae:	b081      	sub	sp, #4
 8004db0:	2600      	movs	r6, #0
 8004db2:	4812      	ldr	r0, [pc, #72]	@ (0x8004dfc)
 8004db4:	4680      	mov	r8, r0
 8004db6:	4812      	ldr	r0, [pc, #72]	@ (0x8004e00)
 8004db8:	0074      	lsls	r4, r6, #1
 8004dba:	1822      	adds	r2, r4, r0
 8004dbc:	2100      	movs	r1, #0
 8004dbe:	8011      	strh	r1, [r2, #0]
 8004dc0:	4643      	mov	r3, r8
 8004dc2:	18e1      	adds	r1, r4, r3
 8004dc4:	8808      	ldrh	r0, [r1, #0]
 8004dc6:	46a1      	mov	r9, r4
 8004dc8:	1c75      	adds	r5, r6, #1
 8004dca:	9500      	str	r5, [sp, #0]
 8004dcc:	2800      	cmp	r0, #0
 8004dce:	d100      	bne.n	0x8004dd2
 8004dd0:	e149      	b.n	0x8005066
 8004dd2:	8809      	ldrh	r1, [r1, #0]
 8004dd4:	480b      	ldr	r0, [pc, #44]	@ (0x8004e04)
 8004dd6:	4281      	cmp	r1, r0
 8004dd8:	d100      	bne.n	0x8004ddc
 8004dda:	e115      	b.n	0x8005008
 8004ddc:	4281      	cmp	r1, r0
 8004dde:	dc23      	bgt.n	0x8004e28
 8004de0:	4809      	ldr	r0, [pc, #36]	@ (0x8004e08)
 8004de2:	4281      	cmp	r1, r0
 8004de4:	d100      	bne.n	0x8004de8
 8004de6:	e139      	b.n	0x800505c
 8004de8:	4281      	cmp	r1, r0
 8004dea:	dc13      	bgt.n	0x8004e14
 8004dec:	4807      	ldr	r0, [pc, #28]	@ (0x8004e0c)
 8004dee:	4281      	cmp	r1, r0
 8004df0:	d044      	beq.n	0x8004e7c
 8004df2:	4807      	ldr	r0, [pc, #28]	@ (0x8004e10)
 8004df4:	4281      	cmp	r1, r0
 8004df6:	d100      	bne.n	0x8004dfa
 8004df8:	e10a      	b.n	0x8005010
 8004dfa:	e134      	b.n	0x8005066
 8004dfc:	2990      	cmp	r1, #144	@ 0x90
 8004dfe:	0300      	lsls	r0, r0, #12
 8004e00:	2880      	cmp	r0, #128	@ 0x80
 8004e02:	0300      	lsls	r0, r0, #12
 8004e04:	5fff      	ldrsh	r7, [r7, r7]
 8004e06:	0000      	movs	r0, r0
 8004e08:	4444      	add	r4, r8
 8004e0a:	0000      	movs	r0, r0
 8004e0c:	2222      	movs	r2, #34	@ 0x22
 8004e0e:	0000      	movs	r0, r0
 8004e10:	2ffe      	cmp	r7, #254	@ 0xfe
 8004e12:	0000      	movs	r0, r0
 8004e14:	4803      	ldr	r0, [pc, #12]	@ (0x8004e24)
 8004e16:	4281      	cmp	r1, r0
 8004e18:	d058      	beq.n	0x8004ecc
 8004e1a:	3011      	adds	r0, #17
 8004e1c:	4281      	cmp	r1, r0
 8004e1e:	d055      	beq.n	0x8004ecc
 8004e20:	e121      	b.n	0x8005066
 8004e22:	0000      	movs	r0, r0
 8004e24:	5555      	strb	r5, [r2, r5]
 8004e26:	0000      	movs	r0, r0
 8004e28:	4806      	ldr	r0, [pc, #24]	@ (0x8004e44)
 8004e2a:	4281      	cmp	r1, r0
 8004e2c:	d100      	bne.n	0x8004e30
 8004e2e:	e0fa      	b.n	0x8005026
 8004e30:	4281      	cmp	r1, r0
 8004e32:	dc0d      	bgt.n	0x8004e50
 8004e34:	4804      	ldr	r0, [pc, #16]	@ (0x8004e48)
 8004e36:	4281      	cmp	r1, r0
 8004e38:	d062      	beq.n	0x8004f00
 8004e3a:	4804      	ldr	r0, [pc, #16]	@ (0x8004e4c)
 8004e3c:	4281      	cmp	r1, r0
 8004e3e:	d100      	bne.n	0x8004e42
 8004e40:	e0ee      	b.n	0x8005020
 8004e42:	e110      	b.n	0x8005066
 8004e44:	aaab      	add	r2, sp, #684	@ 0x2ac
 8004e46:	0000      	movs	r0, r0
 8004e48:	8888      	ldrh	r0, [r1, #4]
 8004e4a:	0000      	movs	r0, r0
 8004e4c:	aaaa      	add	r2, sp, #680	@ 0x2a8
 8004e4e:	0000      	movs	r0, r0
 8004e50:	4804      	ldr	r0, [pc, #16]	@ (0x8004e64)
 8004e52:	4281      	cmp	r1, r0
 8004e54:	d100      	bne.n	0x8004e58
 8004e56:	e101      	b.n	0x800505c
 8004e58:	4281      	cmp	r1, r0
 8004e5a:	dc07      	bgt.n	0x8004e6c
 8004e5c:	4802      	ldr	r0, [pc, #8]	@ (0x8004e68)
 8004e5e:	4281      	cmp	r1, r0
 8004e60:	d03a      	beq.n	0x8004ed8
 8004e62:	e100      	b.n	0x8005066
 8004e64:	cafe      	ldmia	r2, {r1, r2, r3, r4, r5, r6, r7}
 8004e66:	0000      	movs	r0, r0
 8004e68:	bbbb      	cbnz	r3, 0x8004eda
 8004e6a:	0000      	movs	r0, r0
 8004e6c:	4802      	ldr	r0, [pc, #8]	@ (0x8004e78)
 8004e6e:	4281      	cmp	r1, r0
 8004e70:	d100      	bne.n	0x8004e74
 8004e72:	e0e1      	b.n	0x8005038
 8004e74:	e0f7      	b.n	0x8005066
 8004e76:	0000      	movs	r0, r0
 8004e78:	cccc      	ldmia	r4!, {r2, r3, r6, r7}
 8004e7a:	0000      	movs	r0, r0
 8004e7c:	f7ff fd80 	bl	0x8004980
 8004e80:	490f      	ldr	r1, [pc, #60]	@ (0x8004ec0)
 8004e82:	3110      	adds	r1, #16
 8004e84:	480f      	ldr	r0, [pc, #60]	@ (0x8004ec4)
 8004e86:	c81c      	ldmia	r0!, {r2, r3, r4}
 8004e88:	c11c      	stmia	r1!, {r2, r3, r4}
 8004e8a:	c82c      	ldmia	r0!, {r2, r3, r5}
 8004e8c:	c12c      	stmia	r1!, {r2, r3, r5}
 8004e8e:	6800      	ldr	r0, [r0, #0]
 8004e90:	6008      	str	r0, [r1, #0]
 8004e92:	4b0d      	ldr	r3, [pc, #52]	@ (0x8004ec8)
 8004e94:	490a      	ldr	r1, [pc, #40]	@ (0x8004ec0)
 8004e96:	1c18      	adds	r0, r3, #0
 8004e98:	c834      	ldmia	r0!, {r2, r4, r5}
 8004e9a:	c134      	stmia	r1!, {r2, r4, r5}
 8004e9c:	8802      	ldrh	r2, [r0, #0]
 8004e9e:	800a      	strh	r2, [r1, #0]
 8004ea0:	7880      	ldrb	r0, [r0, #2]
 8004ea2:	7088      	strb	r0, [r1, #2]
 8004ea4:	4806      	ldr	r0, [pc, #24]	@ (0x8004ec0)
 8004ea6:	302c      	adds	r0, #44	@ 0x2c
 8004ea8:	cb32      	ldmia	r3!, {r1, r4, r5}
 8004eaa:	c032      	stmia	r0!, {r1, r4, r5}
 8004eac:	8819      	ldrh	r1, [r3, #0]
 8004eae:	8001      	strh	r1, [r0, #0]
 8004eb0:	7899      	ldrb	r1, [r3, #2]
 8004eb2:	7081      	strb	r1, [r0, #2]
 8004eb4:	4802      	ldr	r0, [pc, #8]	@ (0x8004ec0)
 8004eb6:	213c      	movs	r1, #60	@ 0x3c
 8004eb8:	f000 fa90 	bl	0x80053dc
 8004ebc:	e0d3      	b.n	0x8005066
 8004ebe:	0000      	movs	r0, r0
 8004ec0:	2890      	cmp	r0, #144	@ 0x90
 8004ec2:	0300      	lsls	r0, r0, #12
 8004ec4:	2970      	cmp	r1, #112	@ 0x70
 8004ec6:	0300      	lsls	r0, r0, #12
 8004ec8:	be04      	bkpt	0x0004
 8004eca:	081b      	lsrs	r3, r3, #32
 8004ecc:	4901      	ldr	r1, [pc, #4]	@ (0x8004ed4)
 8004ece:	2001      	movs	r0, #1
 8004ed0:	7008      	strb	r0, [r1, #0]
 8004ed2:	e0c8      	b.n	0x8005066
 8004ed4:	29d8      	cmp	r1, #216	@ 0xd8
 8004ed6:	0300      	lsls	r0, r0, #12
 8004ed8:	19a1      	adds	r1, r4, r6
 8004eda:	0089      	lsls	r1, r1, #2
 8004edc:	4a07      	ldr	r2, [pc, #28]	@ (0x8004efc)
 8004ede:	1889      	adds	r1, r1, r2
 8004ee0:	2300      	movs	r3, #0
 8004ee2:	800b      	strh	r3, [r1, #0]
 8004ee4:	4640      	mov	r0, r8
 8004ee6:	3008      	adds	r0, #8
 8004ee8:	1820      	adds	r0, r4, r0
 8004eea:	8800      	ldrh	r0, [r0, #0]
 8004eec:	8048      	strh	r0, [r1, #2]
 8004eee:	4640      	mov	r0, r8
 8004ef0:	3010      	adds	r0, #16
 8004ef2:	1820      	adds	r0, r4, r0
 8004ef4:	8800      	ldrh	r0, [r0, #0]
 8004ef6:	7248      	strb	r0, [r1, #9]
 8004ef8:	e0b5      	b.n	0x8005066
 8004efa:	0000      	movs	r0, r0
 8004efc:	0360      	lsls	r0, r4, #13
 8004efe:	0300      	lsls	r0, r0, #12
 8004f00:	19a0      	adds	r0, r4, r6
 8004f02:	0080      	lsls	r0, r0, #2
 8004f04:	4d0d      	ldr	r5, [pc, #52]	@ (0x8004f3c)
 8004f06:	1943      	adds	r3, r0, r5
 8004f08:	8859      	ldrh	r1, [r3, #2]
 8004f0a:	2080      	movs	r0, #128	@ 0x80
 8004f0c:	0040      	lsls	r0, r0, #1
 8004f0e:	1c2a      	adds	r2, r5, #0
 8004f10:	4692      	mov	sl, r2
 8004f12:	4281      	cmp	r1, r0
 8004f14:	d918      	bls.n	0x8004f48
 8004f16:	4f0a      	ldr	r7, [pc, #40]	@ (0x8004f40)
 8004f18:	2200      	movs	r2, #0
 8004f1a:	4d0a      	ldr	r5, [pc, #40]	@ (0x8004f44)
 8004f1c:	8819      	ldrh	r1, [r3, #0]
 8004f1e:	0849      	lsrs	r1, r1, #1
 8004f20:	1889      	adds	r1, r1, r2
 8004f22:	0049      	lsls	r1, r1, #1
 8004f24:	19c9      	adds	r1, r1, r7
 8004f26:	3201      	adds	r2, #1
 8004f28:	00d0      	lsls	r0, r2, #3
 8004f2a:	1820      	adds	r0, r4, r0
 8004f2c:	1940      	adds	r0, r0, r5
 8004f2e:	8800      	ldrh	r0, [r0, #0]
 8004f30:	8008      	strh	r0, [r1, #0]
 8004f32:	0412      	lsls	r2, r2, #16
 8004f34:	0c12      	lsrs	r2, r2, #16
 8004f36:	2a06      	cmp	r2, #6
 8004f38:	d9f0      	bls.n	0x8004f1c
 8004f3a:	e01c      	b.n	0x8004f76
 8004f3c:	0360      	lsls	r0, r4, #13
 8004f3e:	0300      	lsls	r0, r0, #12
 8004f40:	0000      	movs	r0, r0
 8004f42:	0200      	lsls	r0, r0, #8
 8004f44:	2990      	cmp	r1, #144	@ 0x90
 8004f46:	0300      	lsls	r0, r0, #12
 8004f48:	2200      	movs	r2, #0
 8004f4a:	4d24      	ldr	r5, [pc, #144]	@ (0x8004fdc)
 8004f4c:	46ac      	mov	ip, r5
 8004f4e:	1c25      	adds	r5, r4, #0
 8004f50:	1c1c      	adds	r4, r3, #0
 8004f52:	4f23      	ldr	r7, [pc, #140]	@ (0x8004fe0)
 8004f54:	0233      	lsls	r3, r6, #8
 8004f56:	8821      	ldrh	r1, [r4, #0]
 8004f58:	0849      	lsrs	r1, r1, #1
 8004f5a:	1889      	adds	r1, r1, r2
 8004f5c:	0049      	lsls	r1, r1, #1
 8004f5e:	18c9      	adds	r1, r1, r3
 8004f60:	4461      	add	r1, ip
 8004f62:	3201      	adds	r2, #1
 8004f64:	00d0      	lsls	r0, r2, #3
 8004f66:	1828      	adds	r0, r5, r0
 8004f68:	19c0      	adds	r0, r0, r7
 8004f6a:	8800      	ldrh	r0, [r0, #0]
 8004f6c:	8008      	strh	r0, [r1, #0]
 8004f6e:	0412      	lsls	r2, r2, #16
 8004f70:	0c12      	lsrs	r2, r2, #16
 8004f72:	2a06      	cmp	r2, #6
 8004f74:	d9ef      	bls.n	0x8004f56
 8004f76:	4648      	mov	r0, r9
 8004f78:	1981      	adds	r1, r0, r6
 8004f7a:	0089      	lsls	r1, r1, #2
 8004f7c:	4451      	add	r1, sl
 8004f7e:	8808      	ldrh	r0, [r1, #0]
 8004f80:	300e      	adds	r0, #14
 8004f82:	8008      	strh	r0, [r1, #0]
 8004f84:	0400      	lsls	r0, r0, #16
 8004f86:	0c00      	lsrs	r0, r0, #16
 8004f88:	8849      	ldrh	r1, [r1, #2]
 8004f8a:	4288      	cmp	r0, r1
 8004f8c:	d36b      	bcc.n	0x8005066
 8004f8e:	4815      	ldr	r0, [pc, #84]	@ (0x8004fe4)
 8004f90:	1830      	adds	r0, r6, r0
 8004f92:	7800      	ldrb	r0, [r0, #0]
 8004f94:	2801      	cmp	r0, #1
 8004f96:	d132      	bne.n	0x8004ffe
 8004f98:	0231      	lsls	r1, r6, #8
 8004f9a:	4810      	ldr	r0, [pc, #64]	@ (0x8004fdc)
 8004f9c:	180c      	adds	r4, r1, r0
 8004f9e:	00f1      	lsls	r1, r6, #3
 8004fa0:	1b89      	subs	r1, r1, r6
 8004fa2:	0089      	lsls	r1, r1, #2
 8004fa4:	4810      	ldr	r0, [pc, #64]	@ (0x8004fe8)
 8004fa6:	1809      	adds	r1, r1, r0
 8004fa8:	1c20      	adds	r0, r4, #0
 8004faa:	3010      	adds	r0, #16
 8004fac:	c82c      	ldmia	r0!, {r2, r3, r5}
 8004fae:	c12c      	stmia	r1!, {r2, r3, r5}
 8004fb0:	c82c      	ldmia	r0!, {r2, r3, r5}
 8004fb2:	c12c      	stmia	r1!, {r2, r3, r5}
 8004fb4:	6800      	ldr	r0, [r0, #0]
 8004fb6:	6008      	str	r0, [r1, #0]
 8004fb8:	4d0c      	ldr	r5, [pc, #48]	@ (0x8004fec)
 8004fba:	1c20      	adds	r0, r4, #0
 8004fbc:	1c29      	adds	r1, r5, #0
 8004fbe:	f1ae f94b 	bl	0x81b3258
 8004fc2:	2800      	cmp	r0, #0
 8004fc4:	d106      	bne.n	0x8004fd4
 8004fc6:	1c20      	adds	r0, r4, #0
 8004fc8:	302c      	adds	r0, #44	@ 0x2c
 8004fca:	1c29      	adds	r1, r5, #0
 8004fcc:	f1ae f944 	bl	0x81b3258
 8004fd0:	2800      	cmp	r0, #0
 8004fd2:	d00f      	beq.n	0x8004ff4
 8004fd4:	4806      	ldr	r0, [pc, #24]	@ (0x8004ff0)
 8004fd6:	f7fb f9fd 	bl	0x80003d4
 8004fda:	e044      	b.n	0x8005066
 8004fdc:	2af0      	cmp	r2, #240	@ 0xf0
 8004fde:	0300      	lsls	r0, r0, #12
 8004fe0:	2990      	cmp	r1, #144	@ 0x90
 8004fe2:	0300      	lsls	r0, r0, #12
 8004fe4:	28dc      	cmp	r0, #220	@ 0xdc
 8004fe6:	0300      	lsls	r0, r0, #12
 8004fe8:	28e0      	cmp	r0, #224	@ 0xe0
 8004fea:	0300      	lsls	r0, r0, #12
 8004fec:	be04      	bkpt	0x0004
 8004fee:	081b      	lsrs	r3, r3, #32
 8004ff0:	5bd5      	ldrh	r5, [r2, r7]
 8004ff2:	0800      	lsrs	r0, r0, #32
 8004ff4:	0630      	lsls	r0, r6, #24
 8004ff6:	0e00      	lsrs	r0, r0, #24
 8004ff8:	f7ff feb0 	bl	0x8004d5c
 8004ffc:	e033      	b.n	0x8005066
 8004ffe:	0630      	lsls	r0, r6, #24
 8005000:	0e00      	lsrs	r0, r0, #24
 8005002:	f000 faed 	bl	0x80055e0
 8005006:	e02e      	b.n	0x8005066
 8005008:	4800      	ldr	r0, [pc, #0]	@ (0x800500c)
 800500a:	e002      	b.n	0x8005012
 800500c:	2ae8      	cmp	r2, #232	@ 0xe8
 800500e:	0300      	lsls	r0, r0, #12
 8005010:	4802      	ldr	r0, [pc, #8]	@ (0x800501c)
 8005012:	1830      	adds	r0, r6, r0
 8005014:	2101      	movs	r1, #1
 8005016:	7001      	strb	r1, [r0, #0]
 8005018:	e025      	b.n	0x8005066
 800501a:	0000      	movs	r0, r0
 800501c:	2ae0      	cmp	r2, #224	@ 0xe0
 800501e:	0300      	lsls	r0, r0, #12
 8005020:	f000 fa6e 	bl	0x8005500
 8005024:	e01f      	b.n	0x8005066
 8005026:	0630      	lsls	r0, r6, #24
 8005028:	0e00      	lsrs	r0, r0, #24
 800502a:	4641      	mov	r1, r8
 800502c:	3108      	adds	r1, #8
 800502e:	1861      	adds	r1, r4, r1
 8005030:	8809      	ldrh	r1, [r1, #0]
 8005032:	f049 fbf1 	bl	0x804e818
 8005036:	e016      	b.n	0x8005066
 8005038:	4b07      	ldr	r3, [pc, #28]	@ (0x8005058)
 800503a:	4640      	mov	r0, r8
 800503c:	3008      	adds	r0, #8
 800503e:	1820      	adds	r0, r4, r0
 8005040:	8802      	ldrh	r2, [r0, #0]
 8005042:	00d2      	lsls	r2, r2, #3
 8005044:	18d0      	adds	r0, r2, r3
 8005046:	6801      	ldr	r1, [r0, #0]
 8005048:	3304      	adds	r3, #4
 800504a:	18d2      	adds	r2, r2, r3
 800504c:	8812      	ldrh	r2, [r2, #0]
 800504e:	2000      	movs	r0, #0
 8005050:	f000 fa88 	bl	0x8005564
 8005054:	e007      	b.n	0x8005066
 8005056:	0000      	movs	r0, r0
 8005058:	bdd4      	pop	{r2, r4, r6, r7, pc}
 800505a:	081b      	lsrs	r3, r3, #32
 800505c:	4640      	mov	r0, r8
 800505e:	3008      	adds	r0, #8
 8005060:	1820      	adds	r0, r4, r0
 8005062:	8800      	ldrh	r0, [r0, #0]
 8005064:	8010      	strh	r0, [r2, #0]
 8005066:	9900      	ldr	r1, [sp, #0]
 8005068:	0408      	lsls	r0, r1, #16
 800506a:	0c06      	lsrs	r6, r0, #16
 800506c:	2e03      	cmp	r6, #3
 800506e:	d800      	bhi.n	0x8005072
 8005070:	e6a1      	b.n	0x8004db6
 8005072:	b001      	add	sp, #4
 8005074:	bc38      	pop	{r3, r4, r5}
 8005076:	4698      	mov	r8, r3
 8005078:	46a1      	mov	r9, r4
 800507a:	46aa      	mov	sl, r5
 800507c:	bcf0      	pop	{r4, r5, r6, r7}
 800507e:	bc01      	pop	{r0}
 8005080:	4700      	bx	r0
 8005082:	0000      	movs	r0, r0
 8005084:	b500      	push	{lr}
 8005086:	0400      	lsls	r0, r0, #16
 8005088:	0c02      	lsrs	r2, r0, #16
 800508a:	4807      	ldr	r0, [pc, #28]	@ (0x80050a8)
 800508c:	4282      	cmp	r2, r0
 800508e:	d05d      	beq.n	0x800514c
 8005090:	4282      	cmp	r2, r0
 8005092:	dc23      	bgt.n	0x80050dc
 8005094:	4805      	ldr	r0, [pc, #20]	@ (0x80050ac)
 8005096:	4282      	cmp	r2, r0
 8005098:	d04e      	beq.n	0x8005138
 800509a:	4282      	cmp	r2, r0
 800509c:	dc0c      	bgt.n	0x80050b8
 800509e:	4804      	ldr	r0, [pc, #16]	@ (0x80050b0)
 80050a0:	4282      	cmp	r2, r0
 80050a2:	d03f      	beq.n	0x8005124
 80050a4:	4803      	ldr	r0, [pc, #12]	@ (0x80050b4)
 80050a6:	e012      	b.n	0x80050ce
 80050a8:	6666      	str	r6, [r4, #100]	@ 0x64
 80050aa:	0000      	movs	r0, r0
 80050ac:	4444      	add	r4, r8
 80050ae:	0000      	movs	r0, r0
 80050b0:	2222      	movs	r2, #34	@ 0x22
 80050b2:	0000      	movs	r0, r0
 80050b4:	2ffe      	cmp	r7, #254	@ 0xfe
 80050b6:	0000      	movs	r0, r0
 80050b8:	4803      	ldr	r0, [pc, #12]	@ (0x80050c8)
 80050ba:	4282      	cmp	r2, r0
 80050bc:	d100      	bne.n	0x80050c0
 80050be:	e07d      	b.n	0x80051bc
 80050c0:	4282      	cmp	r2, r0
 80050c2:	dc03      	bgt.n	0x80050cc
 80050c4:	3811      	subs	r0, #17
 80050c6:	e002      	b.n	0x80050ce
 80050c8:	5566      	strb	r6, [r4, r5]
 80050ca:	0000      	movs	r0, r0
 80050cc:	4802      	ldr	r0, [pc, #8]	@ (0x80050d8)
 80050ce:	4282      	cmp	r2, r0
 80050d0:	d100      	bne.n	0x80050d4
 80050d2:	e073      	b.n	0x80051bc
 80050d4:	e083      	b.n	0x80051de
 80050d6:	0000      	movs	r0, r0
 80050d8:	5fff      	ldrsh	r7, [r7, r7]
 80050da:	0000      	movs	r0, r0
 80050dc:	4804      	ldr	r0, [pc, #16]	@ (0x80050f0)
 80050de:	4282      	cmp	r2, r0
 80050e0:	d058      	beq.n	0x8005194
 80050e2:	4282      	cmp	r2, r0
 80050e4:	dc0a      	bgt.n	0x80050fc
 80050e6:	4803      	ldr	r0, [pc, #12]	@ (0x80050f4)
 80050e8:	4282      	cmp	r2, r0
 80050ea:	d035      	beq.n	0x8005158
 80050ec:	4802      	ldr	r0, [pc, #8]	@ (0x80050f8)
 80050ee:	e7ee      	b.n	0x80050ce
 80050f0:	aaab      	add	r2, sp, #684	@ 0x2ac
 80050f2:	0000      	movs	r0, r0
 80050f4:	7777      	strb	r7, [r6, #29]
 80050f6:	0000      	movs	r0, r0
 80050f8:	aaaa      	add	r2, sp, #680	@ 0x2a8
 80050fa:	0000      	movs	r0, r0
 80050fc:	4804      	ldr	r0, [pc, #16]	@ (0x8005110)
 80050fe:	4282      	cmp	r2, r0
 8005100:	d062      	beq.n	0x80051c8
 8005102:	4282      	cmp	r2, r0
 8005104:	dc08      	bgt.n	0x8005118
 8005106:	4803      	ldr	r0, [pc, #12]	@ (0x8005114)
 8005108:	4282      	cmp	r2, r0
 800510a:	d035      	beq.n	0x8005178
 800510c:	e067      	b.n	0x80051de
 800510e:	0000      	movs	r0, r0
 8005110:	cafe      	ldmia	r2, {r1, r2, r3, r4, r5, r6, r7}
 8005112:	0000      	movs	r0, r0
 8005114:	bbbb      	cbnz	r3, 0x8005186
 8005116:	0000      	movs	r0, r0
 8005118:	4801      	ldr	r0, [pc, #4]	@ (0x8005120)
 800511a:	4282      	cmp	r2, r0
 800511c:	d044      	beq.n	0x80051a8
 800511e:	e05e      	b.n	0x80051de
 8005120:	cccc      	ldmia	r4!, {r2, r3, r6, r7}
 8005122:	0000      	movs	r0, r0
 8005124:	4802      	ldr	r0, [pc, #8]	@ (0x8005130)
 8005126:	8002      	strh	r2, [r0, #0]
 8005128:	4902      	ldr	r1, [pc, #8]	@ (0x8005134)
 800512a:	8809      	ldrh	r1, [r1, #0]
 800512c:	e056      	b.n	0x80051dc
 800512e:	0000      	movs	r0, r0
 8005130:	2f00      	cmp	r7, #0
 8005132:	0300      	lsls	r0, r0, #12
 8005134:	2ae4      	cmp	r2, #228	@ 0xe4
 8005136:	0300      	lsls	r0, r0, #12
 8005138:	4802      	ldr	r0, [pc, #8]	@ (0x8005144)
 800513a:	8002      	strh	r2, [r0, #0]
 800513c:	4902      	ldr	r1, [pc, #8]	@ (0x8005148)
 800513e:	8d89      	ldrh	r1, [r1, #44]	@ 0x2c
 8005140:	e04c      	b.n	0x80051dc
 8005142:	0000      	movs	r0, r0
 8005144:	2f00      	cmp	r7, #0
 8005146:	0300      	lsls	r0, r0, #12
 8005148:	16e0      	asrs	r0, r4, #27
 800514a:	0300      	lsls	r0, r0, #12
 800514c:	4801      	ldr	r0, [pc, #4]	@ (0x8005154)
 800514e:	2100      	movs	r1, #0
 8005150:	e043      	b.n	0x80051da
 8005152:	0000      	movs	r0, r0
 8005154:	2f00      	cmp	r7, #0
 8005156:	0300      	lsls	r0, r0, #12
 8005158:	4806      	ldr	r0, [pc, #24]	@ (0x8005174)
 800515a:	8002      	strh	r2, [r0, #0]
 800515c:	2100      	movs	r1, #0
 800515e:	1c03      	adds	r3, r0, #0
 8005160:	22ee      	movs	r2, #238	@ 0xee
 8005162:	3101      	adds	r1, #1
 8005164:	0048      	lsls	r0, r1, #1
 8005166:	18c0      	adds	r0, r0, r3
 8005168:	8002      	strh	r2, [r0, #0]
 800516a:	0609      	lsls	r1, r1, #24
 800516c:	0e09      	lsrs	r1, r1, #24
 800516e:	2904      	cmp	r1, #4
 8005170:	d9f7      	bls.n	0x8005162
 8005172:	e034      	b.n	0x80051de
 8005174:	2f00      	cmp	r7, #0
 8005176:	0300      	lsls	r0, r0, #12
 8005178:	4904      	ldr	r1, [pc, #16]	@ (0x800518c)
 800517a:	800a      	strh	r2, [r1, #0]
 800517c:	4a04      	ldr	r2, [pc, #16]	@ (0x8005190)
 800517e:	8850      	ldrh	r0, [r2, #2]
 8005180:	8048      	strh	r0, [r1, #2]
 8005182:	7a50      	ldrb	r0, [r2, #9]
 8005184:	3080      	adds	r0, #128	@ 0x80
 8005186:	8088      	strh	r0, [r1, #4]
 8005188:	e029      	b.n	0x80051de
 800518a:	0000      	movs	r0, r0
 800518c:	2f00      	cmp	r7, #0
 800518e:	0300      	lsls	r0, r0, #12
 8005190:	0350      	lsls	r0, r2, #13
 8005192:	0300      	lsls	r0, r0, #12
 8005194:	4802      	ldr	r0, [pc, #8]	@ (0x80051a0)
 8005196:	8002      	strh	r2, [r0, #0]
 8005198:	4902      	ldr	r1, [pc, #8]	@ (0x80051a4)
 800519a:	8809      	ldrh	r1, [r1, #0]
 800519c:	e01e      	b.n	0x80051dc
 800519e:	0000      	movs	r0, r0
 80051a0:	2f00      	cmp	r7, #0
 80051a2:	0300      	lsls	r0, r0, #12
 80051a4:	825c      	strh	r4, [r3, #18]
 80051a6:	0203      	lsls	r3, r0, #8
 80051a8:	4802      	ldr	r0, [pc, #8]	@ (0x80051b4)
 80051aa:	8002      	strh	r2, [r0, #0]
 80051ac:	4902      	ldr	r1, [pc, #8]	@ (0x80051b8)
 80051ae:	7809      	ldrb	r1, [r1, #0]
 80051b0:	e014      	b.n	0x80051dc
 80051b2:	0000      	movs	r0, r0
 80051b4:	2f00      	cmp	r7, #0
 80051b6:	0300      	lsls	r0, r0, #12
 80051b8:	2fc4      	cmp	r7, #196	@ 0xc4
 80051ba:	0300      	lsls	r0, r0, #12
 80051bc:	4801      	ldr	r0, [pc, #4]	@ (0x80051c4)
 80051be:	8002      	strh	r2, [r0, #0]
 80051c0:	e00d      	b.n	0x80051de
 80051c2:	0000      	movs	r0, r0
 80051c4:	2f00      	cmp	r7, #0
 80051c6:	0300      	lsls	r0, r0, #12
 80051c8:	4806      	ldr	r0, [pc, #24]	@ (0x80051e4)
 80051ca:	8801      	ldrh	r1, [r0, #0]
 80051cc:	2900      	cmp	r1, #0
 80051ce:	d006      	beq.n	0x80051de
 80051d0:	4805      	ldr	r0, [pc, #20]	@ (0x80051e8)
 80051d2:	7800      	ldrb	r0, [r0, #0]
 80051d4:	2800      	cmp	r0, #0
 80051d6:	d102      	bne.n	0x80051de
 80051d8:	4804      	ldr	r0, [pc, #16]	@ (0x80051ec)
 80051da:	8002      	strh	r2, [r0, #0]
 80051dc:	8041      	strh	r1, [r0, #2]
 80051de:	bc01      	pop	{r0}
 80051e0:	4700      	bx	r0
 80051e2:	0000      	movs	r0, r0
 80051e4:	4788      	blx	r1
 80051e6:	0300      	lsls	r0, r0, #12
 80051e8:	16d4      	asrs	r4, r2, #27
 80051ea:	0300      	lsls	r0, r0, #12
 80051ec:	2f00      	cmp	r7, #0
 80051ee:	0300      	lsls	r0, r0, #12
 80051f0:	4901      	ldr	r1, [pc, #4]	@ (0x80051f8)
 80051f2:	4802      	ldr	r0, [pc, #8]	@ (0x80051fc)
 80051f4:	6008      	str	r0, [r1, #0]
 80051f6:	4770      	bx	lr
 80051f8:	2f30      	cmp	r7, #48	@ 0x30
 80051fa:	0300      	lsls	r0, r0, #12
 80051fc:	5221      	strh	r1, [r4, r0]
 80051fe:	0800      	lsrs	r0, r0, #32
 8005200:	b500      	push	{lr}
 8005202:	4803      	ldr	r0, [pc, #12]	@ (0x8005210)
 8005204:	6801      	ldr	r1, [r0, #0]
 8005206:	4803      	ldr	r0, [pc, #12]	@ (0x8005214)
 8005208:	4281      	cmp	r1, r0
 800520a:	d005      	beq.n	0x8005218
 800520c:	2000      	movs	r0, #0
 800520e:	e004      	b.n	0x800521a
 8005210:	2f30      	cmp	r7, #48	@ 0x30
 8005212:	0300      	lsls	r0, r0, #12
 8005214:	5221      	strh	r1, [r4, r0]
 8005216:	0800      	lsrs	r0, r0, #32
 8005218:	2001      	movs	r0, #1
 800521a:	bc02      	pop	{r1}
 800521c:	4708      	bx	r1
 800521e:	0000      	movs	r0, r0
 8005220:	b500      	push	{lr}
 8005222:	4804      	ldr	r0, [pc, #16]	@ (0x8005234)
 8005224:	7800      	ldrb	r0, [r0, #0]
 8005226:	2801      	cmp	r0, #1
 8005228:	d102      	bne.n	0x8005230
 800522a:	4803      	ldr	r0, [pc, #12]	@ (0x8005238)
 800522c:	f7ff ff2a 	bl	0x8005084
 8005230:	bc01      	pop	{r0}
 8005232:	4700      	bx	r0
 8005234:	2f14      	cmp	r7, #20
 8005236:	0300      	lsls	r0, r0, #12
 8005238:	cafe      	ldmia	r2, {r1, r2, r3, r4, r5, r6, r7}
 800523a:	0000      	movs	r0, r0
 800523c:	4901      	ldr	r1, [pc, #4]	@ (0x8005244)
 800523e:	2000      	movs	r0, #0
 8005240:	6008      	str	r0, [r1, #0]
 8005242:	4770      	bx	lr
 8005244:	2f30      	cmp	r7, #48	@ 0x30
 8005246:	0300      	lsls	r0, r0, #12
 8005248:	4901      	ldr	r1, [pc, #4]	@ (0x8005250)
 800524a:	2000      	movs	r0, #0
 800524c:	6008      	str	r0, [r1, #0]
 800524e:	4770      	bx	lr
 8005250:	2f30      	cmp	r7, #48	@ 0x30
 8005252:	0300      	lsls	r0, r0, #12
 8005254:	4802      	ldr	r0, [pc, #8]	@ (0x8005260)
 8005256:	6800      	ldr	r0, [r0, #0]
 8005258:	211c      	movs	r1, #28
 800525a:	4008      	ands	r0, r1
 800525c:	0880      	lsrs	r0, r0, #2
 800525e:	4770      	bx	lr
 8005260:	29d0      	cmp	r1, #208	@ 0xd0
 8005262:	0300      	lsls	r0, r0, #12
 8005264:	b500      	push	{lr}
 8005266:	4804      	ldr	r0, [pc, #16]	@ (0x8005278)
 8005268:	2100      	movs	r1, #0
 800526a:	6001      	str	r1, [r0, #0]
 800526c:	4803      	ldr	r0, [pc, #12]	@ (0x800527c)
 800526e:	8001      	strh	r1, [r0, #0]
 8005270:	f7ff fc02 	bl	0x8004a78
 8005274:	bc01      	pop	{r0}
 8005276:	4700      	bx	r0
 8005278:	039c      	lsls	r4, r3, #14
 800527a:	0300      	lsls	r0, r0, #12
 800527c:	295c      	cmp	r1, #92	@ 0x5c
 800527e:	0300      	lsls	r0, r0, #12
 8005280:	b5f0      	push	{r4, r5, r6, r7, lr}
 8005282:	2700      	movs	r7, #0
 8005284:	4808      	ldr	r0, [pc, #32]	@ (0x80052a8)
 8005286:	7804      	ldrb	r4, [r0, #0]
 8005288:	2c01      	cmp	r4, #1
 800528a:	d137      	bne.n	0x80052fc
 800528c:	f7ff ffe2 	bl	0x8005254
 8005290:	0600      	lsls	r0, r0, #24
 8005292:	2800      	cmp	r0, #0
 8005294:	d103      	bne.n	0x800529e
 8005296:	4805      	ldr	r0, [pc, #20]	@ (0x80052ac)
 8005298:	7004      	strb	r4, [r0, #0]
 800529a:	f7ff fc31 	bl	0x8004b00
 800529e:	2600      	movs	r6, #0
 80052a0:	4c03      	ldr	r4, [pc, #12]	@ (0x80052b0)
 80052a2:	2500      	movs	r5, #0
 80052a4:	e010      	b.n	0x80052c8
 80052a6:	0000      	movs	r0, r0
 80052a8:	2f14      	cmp	r7, #20
 80052aa:	0300      	lsls	r0, r0, #12
 80052ac:	28cc      	cmp	r0, #204	@ 0xcc
 80052ae:	0300      	lsls	r0, r0, #12
 80052b0:	28e0      	cmp	r0, #224	@ 0xe0
 80052b2:	0300      	lsls	r0, r0, #12
 80052b4:	1c20      	adds	r0, r4, #0
 80052b6:	3014      	adds	r0, #20
 80052b8:	1828      	adds	r0, r5, r0
 80052ba:	6801      	ldr	r1, [r0, #0]
 80052bc:	6960      	ldr	r0, [r4, #20]
 80052be:	4281      	cmp	r1, r0
 80052c0:	d100      	bne.n	0x80052c4
 80052c2:	3701      	adds	r7, #1
 80052c4:	351c      	adds	r5, #28
 80052c6:	3601      	adds	r6, #1
 80052c8:	f7ff ffc4 	bl	0x8005254
 80052cc:	0600      	lsls	r0, r0, #24
 80052ce:	0e00      	lsrs	r0, r0, #24
 80052d0:	4286      	cmp	r6, r0
 80052d2:	dbef      	blt.n	0x80052b4
 80052d4:	f7ff ffbe 	bl	0x8005254
 80052d8:	0600      	lsls	r0, r0, #24
 80052da:	0e00      	lsrs	r0, r0, #24
 80052dc:	4287      	cmp	r7, r0
 80052de:	d105      	bne.n	0x80052ec
 80052e0:	4901      	ldr	r1, [pc, #4]	@ (0x80052e8)
 80052e2:	2001      	movs	r0, #1
 80052e4:	e004      	b.n	0x80052f0
 80052e6:	0000      	movs	r0, r0
 80052e8:	039c      	lsls	r4, r3, #14
 80052ea:	0300      	lsls	r0, r0, #12
 80052ec:	4902      	ldr	r1, [pc, #8]	@ (0x80052f8)
 80052ee:	2003      	movs	r0, #3
 80052f0:	6008      	str	r0, [r1, #0]
 80052f2:	1c0a      	adds	r2, r1, #0
 80052f4:	e00e      	b.n	0x8005314
 80052f6:	0000      	movs	r0, r0
 80052f8:	039c      	lsls	r4, r3, #14
 80052fa:	0300      	lsls	r0, r0, #12
 80052fc:	4807      	ldr	r0, [pc, #28]	@ (0x800531c)
 80052fe:	8801      	ldrh	r1, [r0, #0]
 8005300:	3101      	adds	r1, #1
 8005302:	8001      	strh	r1, [r0, #0]
 8005304:	0409      	lsls	r1, r1, #16
 8005306:	2096      	movs	r0, #150	@ 0x96
 8005308:	0480      	lsls	r0, r0, #18
 800530a:	4a05      	ldr	r2, [pc, #20]	@ (0x8005320)
 800530c:	4281      	cmp	r1, r0
 800530e:	d901      	bls.n	0x8005314
 8005310:	2002      	movs	r0, #2
 8005312:	6010      	str	r0, [r2, #0]
 8005314:	7810      	ldrb	r0, [r2, #0]
 8005316:	bcf0      	pop	{r4, r5, r6, r7}
 8005318:	bc02      	pop	{r1}
 800531a:	4708      	bx	r1
 800531c:	295c      	cmp	r1, #92	@ 0x5c
 800531e:	0300      	lsls	r0, r0, #12
 8005320:	039c      	lsls	r4, r3, #14
 8005322:	0300      	lsls	r0, r0, #12
 8005324:	b570      	push	{r4, r5, r6, lr}
 8005326:	2600      	movs	r6, #0
 8005328:	2400      	movs	r4, #0
 800532a:	4d01      	ldr	r5, [pc, #4]	@ (0x8005330)
 800532c:	e012      	b.n	0x8005354
 800532e:	0000      	movs	r0, r0
 8005330:	28e0      	cmp	r0, #224	@ 0xe0
 8005332:	0300      	lsls	r0, r0, #12
 8005334:	00e0      	lsls	r0, r4, #3
 8005336:	1b00      	subs	r0, r0, r4
 8005338:	0080      	lsls	r0, r0, #2
 800533a:	1c29      	adds	r1, r5, #0
 800533c:	3114      	adds	r1, #20
 800533e:	1840      	adds	r0, r0, r1
 8005340:	6801      	ldr	r1, [r0, #0]
 8005342:	6968      	ldr	r0, [r5, #20]
 8005344:	4281      	cmp	r1, r0
 8005346:	d102      	bne.n	0x800534e
 8005348:	1c70      	adds	r0, r6, #1
 800534a:	0600      	lsls	r0, r0, #24
 800534c:	0e06      	lsrs	r6, r0, #24
 800534e:	1c60      	adds	r0, r4, #1
 8005350:	0600      	lsls	r0, r0, #24
 8005352:	0e04      	lsrs	r4, r0, #24
 8005354:	f7ff ff7e 	bl	0x8005254
 8005358:	0600      	lsls	r0, r0, #24
 800535a:	0e00      	lsrs	r0, r0, #24
 800535c:	4284      	cmp	r4, r0
 800535e:	d3e9      	bcc.n	0x8005334
 8005360:	f7ff ff78 	bl	0x8005254
 8005364:	0600      	lsls	r0, r0, #24
 8005366:	0e00      	lsrs	r0, r0, #24
 8005368:	4286      	cmp	r6, r0
 800536a:	d105      	bne.n	0x8005378
 800536c:	2201      	movs	r2, #1
 800536e:	4801      	ldr	r0, [pc, #4]	@ (0x8005374)
 8005370:	6002      	str	r2, [r0, #0]
 8005372:	e005      	b.n	0x8005380
 8005374:	039c      	lsls	r4, r3, #14
 8005376:	0300      	lsls	r0, r0, #12
 8005378:	2200      	movs	r2, #0
 800537a:	4903      	ldr	r1, [pc, #12]	@ (0x8005388)
 800537c:	2003      	movs	r0, #3
 800537e:	6008      	str	r0, [r1, #0]
 8005380:	1c10      	adds	r0, r2, #0
 8005382:	bc70      	pop	{r4, r5, r6}
 8005384:	bc02      	pop	{r1}
 8005386:	4708      	bx	r1
 8005388:	039c      	lsls	r4, r3, #14
 800538a:	0300      	lsls	r0, r0, #12
 800538c:	0600      	lsls	r0, r0, #24
 800538e:	0e00      	lsrs	r0, r0, #24
 8005390:	4a03      	ldr	r2, [pc, #12]	@ (0x80053a0)
 8005392:	00c1      	lsls	r1, r0, #3
 8005394:	1a09      	subs	r1, r1, r0
 8005396:	0089      	lsls	r1, r1, #2
 8005398:	3204      	adds	r2, #4
 800539a:	1889      	adds	r1, r1, r2
 800539c:	6808      	ldr	r0, [r1, #0]
 800539e:	4770      	bx	lr
 80053a0:	28e0      	cmp	r0, #224	@ 0xe0
 80053a2:	0300      	lsls	r0, r0, #12
 80053a4:	b530      	push	{r4, r5, lr}
 80053a6:	4d07      	ldr	r5, [pc, #28]	@ (0x80053c4)
 80053a8:	2403      	movs	r4, #3
 80053aa:	1c28      	adds	r0, r5, #0
 80053ac:	2100      	movs	r1, #0
 80053ae:	221c      	movs	r2, #28
 80053b0:	f1ad ff28 	bl	0x81b3204
 80053b4:	351c      	adds	r5, #28
 80053b6:	3c01      	subs	r4, #1
 80053b8:	2c00      	cmp	r4, #0
 80053ba:	daf6      	bge.n	0x80053aa
 80053bc:	bc30      	pop	{r4, r5}
 80053be:	bc01      	pop	{r0}
 80053c0:	4700      	bx	r0
 80053c2:	0000      	movs	r0, r0
 80053c4:	28e0      	cmp	r0, #224	@ 0xe0
 80053c6:	0300      	lsls	r0, r0, #12
 80053c8:	4903      	ldr	r1, [pc, #12]	@ (0x80053d8)
 80053ca:	2000      	movs	r0, #0
 80053cc:	7208      	strb	r0, [r1, #8]
 80053ce:	8008      	strh	r0, [r1, #0]
 80053d0:	8048      	strh	r0, [r1, #2]
 80053d2:	6048      	str	r0, [r1, #4]
 80053d4:	4770      	bx	lr
 80053d6:	0000      	movs	r0, r0
 80053d8:	0350      	lsls	r0, r2, #13
 80053da:	0300      	lsls	r0, r0, #12
 80053dc:	b5f0      	push	{r4, r5, r6, r7, lr}
 80053de:	1c07      	adds	r7, r0, #0
 80053e0:	1c0e      	adds	r6, r1, #0
 80053e2:	4c03      	ldr	r4, [pc, #12]	@ (0x80053f0)
 80053e4:	7a25      	ldrb	r5, [r4, #8]
 80053e6:	2d00      	cmp	r5, #0
 80053e8:	d004      	beq.n	0x80053f4
 80053ea:	2000      	movs	r0, #0
 80053ec:	e021      	b.n	0x8005432
 80053ee:	0000      	movs	r0, r0
 80053f0:	0350      	lsls	r0, r2, #13
 80053f2:	0300      	lsls	r0, r0, #12
 80053f4:	f000 f8a0 	bl	0x8005538
 80053f8:	7260      	strb	r0, [r4, #9]
 80053fa:	2001      	movs	r0, #1
 80053fc:	7220      	strb	r0, [r4, #8]
 80053fe:	8066      	strh	r6, [r4, #2]
 8005400:	8025      	strh	r5, [r4, #0]
 8005402:	30ff      	adds	r0, #255	@ 0xff
 8005404:	4286      	cmp	r6, r0
 8005406:	d901      	bls.n	0x800540c
 8005408:	6067      	str	r7, [r4, #4]
 800540a:	e008      	b.n	0x800541e
 800540c:	4d0a      	ldr	r5, [pc, #40]	@ (0x8005438)
 800540e:	42af      	cmp	r7, r5
 8005410:	d004      	beq.n	0x800541c
 8005412:	1c28      	adds	r0, r5, #0
 8005414:	1c39      	adds	r1, r7, #0
 8005416:	1c32      	adds	r2, r6, #0
 8005418:	f1ad fec4 	bl	0x81b31a4
 800541c:	6065      	str	r5, [r4, #4]
 800541e:	4807      	ldr	r0, [pc, #28]	@ (0x800543c)
 8005420:	f7ff fe30 	bl	0x8005084
 8005424:	4906      	ldr	r1, [pc, #24]	@ (0x8005440)
 8005426:	4807      	ldr	r0, [pc, #28]	@ (0x8005444)
 8005428:	6008      	str	r0, [r1, #0]
 800542a:	4907      	ldr	r1, [pc, #28]	@ (0x8005448)
 800542c:	2000      	movs	r0, #0
 800542e:	6008      	str	r0, [r1, #0]
 8005430:	2001      	movs	r0, #1
 8005432:	bcf0      	pop	{r4, r5, r6, r7}
 8005434:	bc02      	pop	{r1}
 8005436:	4708      	bx	r1
 8005438:	29e0      	cmp	r1, #224	@ 0xe0
 800543a:	0300      	lsls	r0, r0, #12
 800543c:	bbbb      	cbnz	r3, 0x80054ae
 800543e:	0000      	movs	r0, r0
 8005440:	2f30      	cmp	r7, #48	@ 0x30
 8005442:	0300      	lsls	r0, r0, #12
 8005444:	544d      	strb	r5, [r1, r1]
 8005446:	0800      	lsrs	r0, r0, #32
 8005448:	0390      	lsls	r0, r2, #14
 800544a:	0300      	lsls	r0, r0, #12
 800544c:	b500      	push	{lr}
 800544e:	4905      	ldr	r1, [pc, #20]	@ (0x8005464)
 8005450:	6808      	ldr	r0, [r1, #0]
 8005452:	3001      	adds	r0, #1
 8005454:	6008      	str	r0, [r1, #0]
 8005456:	2802      	cmp	r0, #2
 8005458:	d902      	bls.n	0x8005460
 800545a:	4903      	ldr	r1, [pc, #12]	@ (0x8005468)
 800545c:	4803      	ldr	r0, [pc, #12]	@ (0x800546c)
 800545e:	6008      	str	r0, [r1, #0]
 8005460:	bc01      	pop	{r0}
 8005462:	4700      	bx	r0
 8005464:	0390      	lsls	r0, r2, #14
 8005466:	0300      	lsls	r0, r0, #12
 8005468:	2f30      	cmp	r7, #48	@ 0x30
 800546a:	0300      	lsls	r0, r0, #12
 800546c:	5471      	strb	r1, [r6, r1]
 800546e:	0800      	lsrs	r0, r0, #32
 8005470:	b570      	push	{r4, r5, r6, lr}
 8005472:	4813      	ldr	r0, [pc, #76]	@ (0x80054c0)
 8005474:	6845      	ldr	r5, [r0, #4]
 8005476:	4a13      	ldr	r2, [pc, #76]	@ (0x80054c4)
 8005478:	4913      	ldr	r1, [pc, #76]	@ (0x80054c8)
 800547a:	8011      	strh	r1, [r2, #0]
 800547c:	2300      	movs	r3, #0
 800547e:	1c04      	adds	r4, r0, #0
 8005480:	1c26      	adds	r6, r4, #0
 8005482:	3202      	adds	r2, #2
 8005484:	0058      	lsls	r0, r3, #1
 8005486:	8831      	ldrh	r1, [r6, #0]
 8005488:	1840      	adds	r0, r0, r1
 800548a:	1940      	adds	r0, r0, r5
 800548c:	7841      	ldrb	r1, [r0, #1]
 800548e:	0209      	lsls	r1, r1, #8
 8005490:	7800      	ldrb	r0, [r0, #0]
 8005492:	4308      	orrs	r0, r1
 8005494:	8010      	strh	r0, [r2, #0]
 8005496:	3202      	adds	r2, #2
 8005498:	3301      	adds	r3, #1
 800549a:	2b06      	cmp	r3, #6
 800549c:	ddf2      	ble.n	0x8005484
 800549e:	8820      	ldrh	r0, [r4, #0]
 80054a0:	300e      	adds	r0, #14
 80054a2:	8020      	strh	r0, [r4, #0]
 80054a4:	8861      	ldrh	r1, [r4, #2]
 80054a6:	0400      	lsls	r0, r0, #16
 80054a8:	0c00      	lsrs	r0, r0, #16
 80054aa:	4281      	cmp	r1, r0
 80054ac:	d804      	bhi.n	0x80054b8
 80054ae:	2000      	movs	r0, #0
 80054b0:	7220      	strb	r0, [r4, #8]
 80054b2:	4906      	ldr	r1, [pc, #24]	@ (0x80054cc)
 80054b4:	4806      	ldr	r0, [pc, #24]	@ (0x80054d0)
 80054b6:	6008      	str	r0, [r1, #0]
 80054b8:	bc70      	pop	{r4, r5, r6}
 80054ba:	bc01      	pop	{r0}
 80054bc:	4700      	bx	r0
 80054be:	0000      	movs	r0, r0
 80054c0:	0350      	lsls	r0, r2, #13
 80054c2:	0300      	lsls	r0, r0, #12
 80054c4:	2f00      	cmp	r7, #0
 80054c6:	0300      	lsls	r0, r0, #12
 80054c8:	8888      	ldrh	r0, [r1, #4]
 80054ca:	0000      	movs	r0, r0
 80054cc:	2f30      	cmp	r7, #48	@ 0x30
 80054ce:	0300      	lsls	r0, r0, #12
 80054d0:	54d5      	strb	r5, [r2, r3]
 80054d2:	0800      	lsrs	r0, r0, #32
 80054d4:	4901      	ldr	r1, [pc, #4]	@ (0x80054dc)
 80054d6:	2000      	movs	r0, #0
 80054d8:	6008      	str	r0, [r1, #0]
 80054da:	4770      	bx	lr
 80054dc:	2f30      	cmp	r7, #48	@ 0x30
 80054de:	0300      	lsls	r0, r0, #12
 80054e0:	b500      	push	{lr}
 80054e2:	f000 f829 	bl	0x8005538
 80054e6:	4804      	ldr	r0, [pc, #16]	@ (0x80054f8)
 80054e8:	f7ff fdcc 	bl	0x8005084
 80054ec:	4903      	ldr	r1, [pc, #12]	@ (0x80054fc)
 80054ee:	6808      	ldr	r0, [r1, #0]
 80054f0:	3001      	adds	r0, #1
 80054f2:	6008      	str	r0, [r1, #0]
 80054f4:	bc01      	pop	{r0}
 80054f6:	4700      	bx	r0
 80054f8:	4444      	add	r4, r8
 80054fa:	0000      	movs	r0, r0
 80054fc:	361c      	adds	r6, #28
 80054fe:	0202      	lsls	r2, r0, #8
 8005500:	4903      	ldr	r1, [pc, #12]	@ (0x8005510)
 8005502:	2000      	movs	r0, #0
 8005504:	6008      	str	r0, [r1, #0]
 8005506:	4903      	ldr	r1, [pc, #12]	@ (0x8005514)
 8005508:	4803      	ldr	r0, [pc, #12]	@ (0x8005518)
 800550a:	6008      	str	r0, [r1, #0]
 800550c:	4770      	bx	lr
 800550e:	0000      	movs	r0, r0
 8005510:	361c      	adds	r6, #28
 8005512:	0202      	lsls	r2, r0, #8
 8005514:	2f30      	cmp	r7, #48	@ 0x30
 8005516:	0300      	lsls	r0, r0, #12
 8005518:	54e1      	strb	r1, [r4, r3]
 800551a:	0800      	lsrs	r0, r0, #32
 800551c:	4801      	ldr	r0, [pc, #4]	@ (0x8005524)
 800551e:	6800      	ldr	r0, [r0, #0]
 8005520:	4770      	bx	lr
 8005522:	0000      	movs	r0, r0
 8005524:	361c      	adds	r6, #28
 8005526:	0202      	lsls	r2, r0, #8
 8005528:	b500      	push	{lr}
 800552a:	4802      	ldr	r0, [pc, #8]	@ (0x8005534)
 800552c:	f7ff fdaa 	bl	0x8005084
 8005530:	bc01      	pop	{r0}
 8005532:	4700      	bx	r0
 8005534:	aaaa      	add	r2, sp, #680	@ 0x2a8
 8005536:	0000      	movs	r0, r0
 8005538:	4802      	ldr	r0, [pc, #8]	@ (0x8005544)
 800553a:	6800      	ldr	r0, [r0, #0]
 800553c:	0680      	lsls	r0, r0, #26
 800553e:	0f80      	lsrs	r0, r0, #30
 8005540:	4770      	bx	lr
 8005542:	0000      	movs	r0, r0
 8005544:	0128      	lsls	r0, r5, #4
 8005546:	0400      	lsls	r0, r0, #16
 8005548:	b500      	push	{lr}
 800554a:	f7ff fff5 	bl	0x8005538
 800554e:	1c01      	adds	r1, r0, #0
 8005550:	0609      	lsls	r1, r1, #24
 8005552:	0e09      	lsrs	r1, r1, #24
 8005554:	2001      	movs	r0, #1
 8005556:	4088      	lsls	r0, r1
 8005558:	210f      	movs	r1, #15
 800555a:	4048      	eors	r0, r1
 800555c:	0600      	lsls	r0, r0, #24
 800555e:	0e00      	lsrs	r0, r0, #24
 8005560:	bc02      	pop	{r1}
 8005562:	4708      	bx	r1
 8005564:	b500      	push	{lr}
 8005566:	1c08      	adds	r0, r1, #0
 8005568:	0411      	lsls	r1, r2, #16
 800556a:	0c09      	lsrs	r1, r1, #16
 800556c:	f7ff ff36 	bl	0x80053dc
 8005570:	0600      	lsls	r0, r0, #24
 8005572:	0e00      	lsrs	r0, r0, #24
 8005574:	bc02      	pop	{r1}
 8005576:	4708      	bx	r1
 8005578:	b500      	push	{lr}
 800557a:	0600      	lsls	r0, r0, #24
 800557c:	0e01      	lsrs	r1, r0, #24
 800557e:	4803      	ldr	r0, [pc, #12]	@ (0x800558c)
 8005580:	6800      	ldr	r0, [r0, #0]
 8005582:	2800      	cmp	r0, #0
 8005584:	d004      	beq.n	0x8005590
 8005586:	2000      	movs	r0, #0
 8005588:	e008      	b.n	0x800559c
 800558a:	0000      	movs	r0, r0
 800558c:	2f30      	cmp	r7, #48	@ 0x30
 800558e:	0300      	lsls	r0, r0, #12
 8005590:	4803      	ldr	r0, [pc, #12]	@ (0x80055a0)
 8005592:	7001      	strb	r1, [r0, #0]
 8005594:	4803      	ldr	r0, [pc, #12]	@ (0x80055a4)
 8005596:	f7ff fd75 	bl	0x8005084
 800559a:	2001      	movs	r0, #1
 800559c:	bc02      	pop	{r1}
 800559e:	4708      	bx	r1
 80055a0:	2fc4      	cmp	r7, #196	@ 0xc4
 80055a2:	0300      	lsls	r0, r0, #12
 80055a4:	cccc      	ldmia	r4!, {r2, r3, r6, r7}
 80055a6:	0000      	movs	r0, r0
 80055a8:	b500      	push	{lr}
 80055aa:	2100      	movs	r1, #0
 80055ac:	4803      	ldr	r0, [pc, #12]	@ (0x80055bc)
 80055ae:	6800      	ldr	r0, [r0, #0]
 80055b0:	2800      	cmp	r0, #0
 80055b2:	d100      	bne.n	0x80055b6
 80055b4:	2101      	movs	r1, #1
 80055b6:	1c08      	adds	r0, r1, #0
 80055b8:	bc02      	pop	{r1}
 80055ba:	4708      	bx	r1
 80055bc:	2f30      	cmp	r7, #48	@ 0x30
 80055be:	0300      	lsls	r0, r0, #12
 80055c0:	4a06      	ldr	r2, [pc, #24]	@ (0x80055dc)
 80055c2:	78d0      	ldrb	r0, [r2, #3]
 80055c4:	00c0      	lsls	r0, r0, #3
 80055c6:	7891      	ldrb	r1, [r2, #2]
 80055c8:	0089      	lsls	r1, r1, #2
 80055ca:	4308      	orrs	r0, r1
 80055cc:	7851      	ldrb	r1, [r2, #1]
 80055ce:	0049      	lsls	r1, r1, #1
 80055d0:	4308      	orrs	r0, r1
 80055d2:	7811      	ldrb	r1, [r2, #0]
 80055d4:	4308      	orrs	r0, r1
 80055d6:	0600      	lsls	r0, r0, #24
 80055d8:	0e00      	lsrs	r0, r0, #24
 80055da:	4770      	bx	lr
 80055dc:	2950      	cmp	r1, #80	@ 0x50
 80055de:	0300      	lsls	r0, r0, #12
 80055e0:	0600      	lsls	r0, r0, #24
 80055e2:	0e00      	lsrs	r0, r0, #24
 80055e4:	4902      	ldr	r1, [pc, #8]	@ (0x80055f0)
 80055e6:	1840      	adds	r0, r0, r1
 80055e8:	2101      	movs	r1, #1
 80055ea:	7001      	strb	r1, [r0, #0]
 80055ec:	4770      	bx	lr
 80055ee:	0000      	movs	r0, r0
 80055f0:	2950      	cmp	r1, #80	@ 0x50
 80055f2:	0300      	lsls	r0, r0, #12
 80055f4:	b500      	push	{lr}
 80055f6:	4904      	ldr	r1, [pc, #16]	@ (0x8005608)
 80055f8:	2200      	movs	r2, #0
 80055fa:	1cc8      	adds	r0, r1, #3
 80055fc:	7002      	strb	r2, [r0, #0]
 80055fe:	3801      	subs	r0, #1
 8005600:	4288      	cmp	r0, r1
 8005602:	dafb      	bge.n	0x80055fc
 8005604:	bc01      	pop	{r0}
 8005606:	4700      	bx	r0
 8005608:	2950      	cmp	r1, #80	@ 0x50
 800560a:	0300      	lsls	r0, r0, #12
 800560c:	b500      	push	{lr}
 800560e:	0600      	lsls	r0, r0, #24
 8005610:	0e00      	lsrs	r0, r0, #24
 8005612:	4904      	ldr	r1, [pc, #16]	@ (0x8005624)
 8005614:	1841      	adds	r1, r0, r1
 8005616:	7808      	ldrb	r0, [r1, #0]
 8005618:	2800      	cmp	r0, #0
 800561a:	d001      	beq.n	0x8005620
 800561c:	2000      	movs	r0, #0
 800561e:	7008      	strb	r0, [r1, #0]
 8005620:	bc01      	pop	{r0}
 8005622:	4700      	bx	r0
 8005624:	2950      	cmp	r1, #80	@ 0x50
 8005626:	0300      	lsls	r0, r0, #12
 8005628:	b500      	push	{lr}
 800562a:	4807      	ldr	r0, [pc, #28]	@ (0x8005648)
 800562c:	6801      	ldr	r1, [r0, #0]
 800562e:	2020      	movs	r0, #32
 8005630:	4008      	ands	r0, r1
 8005632:	2800      	cmp	r0, #0
 8005634:	d006      	beq.n	0x8005644
 8005636:	201c      	movs	r0, #28
 8005638:	4001      	ands	r1, r0
 800563a:	2904      	cmp	r1, #4
 800563c:	d902      	bls.n	0x8005644
 800563e:	4903      	ldr	r1, [pc, #12]	@ (0x800564c)
 8005640:	2001      	movs	r0, #1
 8005642:	7008      	strb	r0, [r1, #0]
 8005644:	bc01      	pop	{r0}
 8005646:	4700      	bx	r0
 8005648:	29d0      	cmp	r1, #208	@ 0xd0
 800564a:	0300      	lsls	r0, r0, #12
 800564c:	2fb0      	cmp	r7, #176	@ 0xb0
 800564e:	0300      	lsls	r0, r0, #12
 8005650:	b510      	push	{r4, lr}
 8005652:	1c04      	adds	r4, r0, #0
 8005654:	0409      	lsls	r1, r1, #16
 8005656:	2300      	movs	r3, #0
 8005658:	2200      	movs	r2, #0
 800565a:	0c49      	lsrs	r1, r1, #17
 800565c:	428b      	cmp	r3, r1
 800565e:	d20a      	bcs.n	0x8005676
 8005660:	0050      	lsls	r0, r2, #1
 8005662:	1900      	adds	r0, r0, r4
 8005664:	8800      	ldrh	r0, [r0, #0]
 8005666:	1818      	adds	r0, r3, r0
 8005668:	0400      	lsls	r0, r0, #16
 800566a:	0c03      	lsrs	r3, r0, #16
 800566c:	1c50      	adds	r0, r2, #1
 800566e:	0400      	lsls	r0, r0, #16
 8005670:	0c02      	lsrs	r2, r0, #16
 8005672:	428a      	cmp	r2, r1
 8005674:	d3f4      	bcc.n	0x8005660
 8005676:	1c18      	adds	r0, r3, #0
 8005678:	bc10      	pop	{r4}
 800567a:	bc02      	pop	{r1}
 800567c:	4708      	bx	r1
 800567e:	0000      	movs	r0, r0
 8005680:	b530      	push	{r4, r5, lr}
 8005682:	0600      	lsls	r0, r0, #24
 8005684:	0e00      	lsrs	r0, r0, #24
 8005686:	0609      	lsls	r1, r1, #24
 8005688:	0e09      	lsrs	r1, r1, #24
 800568a:	0612      	lsls	r2, r2, #24
 800568c:	4c08      	ldr	r4, [pc, #32]	@ (0x80056b0)
 800568e:	6823      	ldr	r3, [r4, #0]
 8005690:	02db      	lsls	r3, r3, #11
 8005692:	25c0      	movs	r5, #192	@ 0xc0
 8005694:	04ed      	lsls	r5, r5, #19
 8005696:	195b      	adds	r3, r3, r5
 8005698:	0cd2      	lsrs	r2, r2, #19
 800569a:	1852      	adds	r2, r2, r1
 800569c:	0052      	lsls	r2, r2, #1
 800569e:	18d2      	adds	r2, r2, r3
 80056a0:	6861      	ldr	r1, [r4, #4]
 80056a2:	0309      	lsls	r1, r1, #12
 80056a4:	3001      	adds	r0, #1
 80056a6:	4301      	orrs	r1, r0
 80056a8:	8011      	strh	r1, [r2, #0]
 80056aa:	bc30      	pop	{r4, r5}
 80056ac:	bc01      	pop	{r0}
 80056ae:	4700      	bx	r0
 80056b0:	2f20      	cmp	r7, #32
 80056b2:	0300      	lsls	r0, r0, #12
 80056b4:	b5f0      	push	{r4, r5, r6, r7, lr}
 80056b6:	b084      	sub	sp, #16
 80056b8:	1c05      	adds	r5, r0, #0
 80056ba:	0609      	lsls	r1, r1, #24
 80056bc:	0e0e      	lsrs	r6, r1, #24
 80056be:	0612      	lsls	r2, r2, #24
 80056c0:	0e17      	lsrs	r7, r2, #24
 80056c2:	061b      	lsls	r3, r3, #24
 80056c4:	0e1b      	lsrs	r3, r3, #24
 80056c6:	2400      	movs	r4, #0
 80056c8:	429c      	cmp	r4, r3
 80056ca:	da09      	bge.n	0x80056e0
 80056cc:	220f      	movs	r2, #15
 80056ce:	4668      	mov	r0, sp
 80056d0:	1901      	adds	r1, r0, r4
 80056d2:	1c28      	adds	r0, r5, #0
 80056d4:	4010      	ands	r0, r2
 80056d6:	7008      	strb	r0, [r1, #0]
 80056d8:	092d      	lsrs	r5, r5, #4
 80056da:	3401      	adds	r4, #1
 80056dc:	429c      	cmp	r4, r3
 80056de:	dbf6      	blt.n	0x80056ce
 80056e0:	1e5c      	subs	r4, r3, #1
 80056e2:	2c00      	cmp	r4, #0
 80056e4:	db0c      	blt.n	0x8005700
 80056e6:	4669      	mov	r1, sp
 80056e8:	1908      	adds	r0, r1, r4
 80056ea:	7800      	ldrb	r0, [r0, #0]
 80056ec:	1c31      	adds	r1, r6, #0
 80056ee:	1c3a      	adds	r2, r7, #0
 80056f0:	f7ff ffc6 	bl	0x8005680
 80056f4:	1c70      	adds	r0, r6, #1
 80056f6:	0600      	lsls	r0, r0, #24
 80056f8:	0e06      	lsrs	r6, r0, #24
 80056fa:	3c01      	subs	r4, #1
 80056fc:	2c00      	cmp	r4, #0
 80056fe:	daf2      	bge.n	0x80056e6
 8005700:	b004      	add	sp, #16
 8005702:	bcf0      	pop	{r4, r5, r6, r7}
 8005704:	bc01      	pop	{r0}
 8005706:	4700      	bx	r0
 8005708:	b500      	push	{lr}
 800570a:	4807      	ldr	r0, [pc, #28]	@ (0x8005728)
 800570c:	6800      	ldr	r0, [r0, #0]
 800570e:	2120      	movs	r1, #32
 8005710:	4008      	ands	r0, r1
 8005712:	2800      	cmp	r0, #0
 8005714:	d002      	beq.n	0x800571c
 8005716:	4805      	ldr	r0, [pc, #20]	@ (0x800572c)
 8005718:	f7ff fcb4 	bl	0x8005084
 800571c:	4904      	ldr	r1, [pc, #16]	@ (0x8005730)
 800571e:	2000      	movs	r0, #0
 8005720:	6008      	str	r0, [r1, #0]
 8005722:	bc01      	pop	{r0}
 8005724:	4700      	bx	r0
 8005726:	0000      	movs	r0, r0
 8005728:	29d0      	cmp	r1, #208	@ 0xd0
 800572a:	0300      	lsls	r0, r0, #12
 800572c:	2222      	movs	r2, #34	@ 0x22
 800572e:	0000      	movs	r0, r0
 8005730:	2f30      	cmp	r7, #48	@ 0x30
 8005732:	0300      	lsls	r0, r0, #12
 8005734:	b570      	push	{r4, r5, r6, lr}
 8005736:	4842      	ldr	r0, [pc, #264]	@ (0x8005840)
 8005738:	7800      	ldrb	r0, [r0, #0]
 800573a:	2102      	movs	r1, #2
 800573c:	2201      	movs	r2, #1
 800573e:	2302      	movs	r3, #2
 8005740:	f7ff ffb8 	bl	0x80056b4
 8005744:	4c3f      	ldr	r4, [pc, #252]	@ (0x8005844)
 8005746:	6820      	ldr	r0, [r4, #0]
 8005748:	210f      	movs	r1, #15
 800574a:	2201      	movs	r2, #1
 800574c:	2308      	movs	r3, #8
 800574e:	f7ff ffb1 	bl	0x80056b4
 8005752:	483d      	ldr	r0, [pc, #244]	@ (0x8005848)
 8005754:	7840      	ldrb	r0, [r0, #1]
 8005756:	2102      	movs	r1, #2
 8005758:	220a      	movs	r2, #10
 800575a:	2302      	movs	r3, #2
 800575c:	f7ff ffaa 	bl	0x80056b4
 8005760:	6820      	ldr	r0, [r4, #0]
 8005762:	211c      	movs	r1, #28
 8005764:	4008      	ands	r0, r1
 8005766:	0880      	lsrs	r0, r0, #2
 8005768:	210f      	movs	r1, #15
 800576a:	220a      	movs	r2, #10
 800576c:	2302      	movs	r3, #2
 800576e:	f7ff ffa1 	bl	0x80056b4
 8005772:	f7ff fee1 	bl	0x8005538
 8005776:	0600      	lsls	r0, r0, #24
 8005778:	0e00      	lsrs	r0, r0, #24
 800577a:	210f      	movs	r1, #15
 800577c:	220c      	movs	r2, #12
 800577e:	2302      	movs	r3, #2
 8005780:	f7ff ff98 	bl	0x80056b4
 8005784:	4831      	ldr	r0, [pc, #196]	@ (0x800584c)
 8005786:	7800      	ldrb	r0, [r0, #0]
 8005788:	2119      	movs	r1, #25
 800578a:	2201      	movs	r2, #1
 800578c:	2302      	movs	r3, #2
 800578e:	f7ff ff91 	bl	0x80056b4
 8005792:	482f      	ldr	r0, [pc, #188]	@ (0x8005850)
 8005794:	7800      	ldrb	r0, [r0, #0]
 8005796:	2119      	movs	r1, #25
 8005798:	2202      	movs	r2, #2
 800579a:	2302      	movs	r3, #2
 800579c:	f7ff ff8a 	bl	0x80056b4
 80057a0:	f7ff ff0e 	bl	0x80055c0
 80057a4:	0600      	lsls	r0, r0, #24
 80057a6:	0e00      	lsrs	r0, r0, #24
 80057a8:	210f      	movs	r1, #15
 80057aa:	2205      	movs	r2, #5
 80057ac:	2302      	movs	r3, #2
 80057ae:	f7ff ff81 	bl	0x80056b4
 80057b2:	4828      	ldr	r0, [pc, #160]	@ (0x8005854)
 80057b4:	6800      	ldr	r0, [r0, #0]
 80057b6:	2102      	movs	r1, #2
 80057b8:	220c      	movs	r2, #12
 80057ba:	2308      	movs	r3, #8
 80057bc:	f7ff ff7a 	bl	0x80056b4
 80057c0:	4825      	ldr	r0, [pc, #148]	@ (0x8005858)
 80057c2:	6800      	ldr	r0, [r0, #0]
 80057c4:	2102      	movs	r1, #2
 80057c6:	220d      	movs	r2, #13
 80057c8:	2308      	movs	r3, #8
 80057ca:	f7ff ff73 	bl	0x80056b4
 80057ce:	f000 fa7b 	bl	0x8005cc8
 80057d2:	0600      	lsls	r0, r0, #24
 80057d4:	0e00      	lsrs	r0, r0, #24
 80057d6:	2119      	movs	r1, #25
 80057d8:	2205      	movs	r2, #5
 80057da:	2301      	movs	r3, #1
 80057dc:	f7ff ff6a 	bl	0x80056b4
 80057e0:	f000 fa7a 	bl	0x8005cd8
 80057e4:	0600      	lsls	r0, r0, #24
 80057e6:	0e00      	lsrs	r0, r0, #24
 80057e8:	2119      	movs	r1, #25
 80057ea:	2206      	movs	r2, #6
 80057ec:	2301      	movs	r3, #1
 80057ee:	f7ff ff61 	bl	0x80056b4
 80057f2:	f000 fa85 	bl	0x8005d00
 80057f6:	0600      	lsls	r0, r0, #24
 80057f8:	0e00      	lsrs	r0, r0, #24
 80057fa:	2119      	movs	r1, #25
 80057fc:	2207      	movs	r2, #7
 80057fe:	2301      	movs	r3, #1
 8005800:	f7ff ff58 	bl	0x80056b4
 8005804:	f000 fa8a 	bl	0x8005d1c
 8005808:	0600      	lsls	r0, r0, #24
 800580a:	0e00      	lsrs	r0, r0, #24
 800580c:	2119      	movs	r1, #25
 800580e:	2208      	movs	r2, #8
 8005810:	2301      	movs	r3, #1
 8005812:	f7ff ff4f 	bl	0x80056b4
 8005816:	2600      	movs	r6, #0
 8005818:	2580      	movs	r5, #128	@ 0x80
 800581a:	04ed      	lsls	r5, r5, #19
 800581c:	4c0f      	ldr	r4, [pc, #60]	@ (0x800585c)
 800581e:	8820      	ldrh	r0, [r4, #0]
 8005820:	0e2a      	lsrs	r2, r5, #24
 8005822:	210a      	movs	r1, #10
 8005824:	2304      	movs	r3, #4
 8005826:	f7ff ff45 	bl	0x80056b4
 800582a:	2080      	movs	r0, #128	@ 0x80
 800582c:	0440      	lsls	r0, r0, #17
 800582e:	182d      	adds	r5, r5, r0
 8005830:	3402      	adds	r4, #2
 8005832:	3601      	adds	r6, #1
 8005834:	2e03      	cmp	r6, #3
 8005836:	ddf2      	ble.n	0x800581e
 8005838:	bc70      	pop	{r4, r5, r6}
 800583a:	bc01      	pop	{r0}
 800583c:	4700      	bx	r0
 800583e:	0000      	movs	r0, r0
 8005840:	2fb0      	cmp	r7, #176	@ 0xb0
 8005842:	0300      	lsls	r0, r0, #12
 8005844:	29d0      	cmp	r1, #208	@ 0xd0
 8005846:	0300      	lsls	r0, r0, #12
 8005848:	2fe0      	cmp	r7, #224	@ 0xe0
 800584a:	0300      	lsls	r0, r0, #12
 800584c:	2fd0      	cmp	r7, #208	@ 0xd0
 800584e:	0300      	lsls	r0, r0, #12
 8005850:	3fa0      	subs	r7, #160	@ 0xa0
 8005852:	0300      	lsls	r0, r0, #12
 8005854:	2888      	cmp	r0, #136	@ 0x88
 8005856:	0300      	lsls	r0, r0, #12
 8005858:	28d4      	cmp	r0, #212	@ 0xd4
 800585a:	0300      	lsls	r0, r0, #12
 800585c:	2fb8      	cmp	r7, #184	@ 0xb8
 800585e:	0300      	lsls	r0, r0, #12
 8005860:	4a02      	ldr	r2, [pc, #8]	@ (0x800586c)
 8005862:	6010      	str	r0, [r2, #0]
 8005864:	4802      	ldr	r0, [pc, #8]	@ (0x8005870)
 8005866:	6001      	str	r1, [r0, #0]
 8005868:	4770      	bx	lr
 800586a:	0000      	movs	r0, r0
 800586c:	2888      	cmp	r0, #136	@ 0x88
 800586e:	0300      	lsls	r0, r0, #12
 8005870:	28d4      	cmp	r0, #212	@ 0xd4
 8005872:	0300      	lsls	r0, r0, #12
 8005874:	b510      	push	{r4, lr}
 8005876:	2100      	movs	r1, #0
 8005878:	2200      	movs	r2, #0
 800587a:	4809      	ldr	r0, [pc, #36]	@ (0x80058a0)
 800587c:	7800      	ldrb	r0, [r0, #0]
 800587e:	4281      	cmp	r1, r0
 8005880:	da09      	bge.n	0x8005896
 8005882:	2401      	movs	r4, #1
 8005884:	1c03      	adds	r3, r0, #0
 8005886:	1c20      	adds	r0, r4, #0
 8005888:	4090      	lsls	r0, r2
 800588a:	4301      	orrs	r1, r0
 800588c:	0608      	lsls	r0, r1, #24
 800588e:	0e01      	lsrs	r1, r0, #24
 8005890:	3201      	adds	r2, #1
 8005892:	429a      	cmp	r2, r3
 8005894:	dbf7      	blt.n	0x8005886
 8005896:	1c08      	adds	r0, r1, #0
 8005898:	bc10      	pop	{r4}
 800589a:	bc02      	pop	{r1}
 800589c:	4708      	bx	r1
 800589e:	0000      	movs	r0, r0
 80058a0:	2ef4      	cmp	r6, #244	@ 0xf4
 80058a2:	0300      	lsls	r0, r0, #12
 80058a4:	b5f0      	push	{r4, r5, r6, r7, lr}
 80058a6:	490c      	ldr	r1, [pc, #48]	@ (0x80058d8)
 80058a8:	7008      	strb	r0, [r1, #0]
 80058aa:	f7ff fe45 	bl	0x8005538
 80058ae:	490b      	ldr	r1, [pc, #44]	@ (0x80058dc)
 80058b0:	7008      	strb	r0, [r1, #0]
 80058b2:	4c0b      	ldr	r4, [pc, #44]	@ (0x80058e0)
 80058b4:	4b0b      	ldr	r3, [pc, #44]	@ (0x80058e4)
 80058b6:	2203      	movs	r2, #3
 80058b8:	1c18      	adds	r0, r3, #0
 80058ba:	1c21      	adds	r1, r4, #0
 80058bc:	c9e0      	ldmia	r1!, {r5, r6, r7}
 80058be:	c0e0      	stmia	r0!, {r5, r6, r7}
 80058c0:	c9e0      	ldmia	r1!, {r5, r6, r7}
 80058c2:	c0e0      	stmia	r0!, {r5, r6, r7}
 80058c4:	6809      	ldr	r1, [r1, #0]
 80058c6:	6001      	str	r1, [r0, #0]
 80058c8:	341c      	adds	r4, #28
 80058ca:	331c      	adds	r3, #28
 80058cc:	3a01      	subs	r2, #1
 80058ce:	2a00      	cmp	r2, #0
 80058d0:	daf2      	bge.n	0x80058b8
 80058d2:	bcf0      	pop	{r4, r5, r6, r7}
 80058d4:	bc01      	pop	{r0}
 80058d6:	4700      	bx	r0
 80058d8:	2ef4      	cmp	r6, #244	@ 0xf4
 80058da:	0300      	lsls	r0, r0, #12
 80058dc:	2f10      	cmp	r7, #16
 80058de:	0300      	lsls	r0, r0, #12
 80058e0:	28e0      	cmp	r0, #224	@ 0xe0
 80058e2:	0300      	lsls	r0, r0, #12
 80058e4:	2f40      	cmp	r7, #64	@ 0x40
 80058e6:	0300      	lsls	r0, r0, #12
 80058e8:	4801      	ldr	r0, [pc, #4]	@ (0x80058f0)
 80058ea:	7800      	ldrb	r0, [r0, #0]
 80058ec:	4770      	bx	lr
 80058ee:	0000      	movs	r0, r0
 80058f0:	2ef4      	cmp	r6, #244	@ 0xf4
 80058f2:	0300      	lsls	r0, r0, #12
 80058f4:	4801      	ldr	r0, [pc, #4]	@ (0x80058fc)
 80058f6:	7800      	ldrb	r0, [r0, #0]
 80058f8:	4770      	bx	lr
 80058fa:	0000      	movs	r0, r0
 80058fc:	2f10      	cmp	r7, #16
 80058fe:	0300      	lsls	r0, r0, #12
 8005900:	b570      	push	{r4, r5, r6, lr}
 8005902:	2500      	movs	r5, #0
 8005904:	480b      	ldr	r0, [pc, #44]	@ (0x8005934)
 8005906:	7802      	ldrb	r2, [r0, #0]
 8005908:	1c06      	adds	r6, r0, #0
 800590a:	4295      	cmp	r5, r2
 800590c:	da0d      	bge.n	0x800592a
 800590e:	490a      	ldr	r1, [pc, #40]	@ (0x8005938)
 8005910:	480a      	ldr	r0, [pc, #40]	@ (0x800593c)
 8005912:	1d04      	adds	r4, r0, #4
 8005914:	1d0b      	adds	r3, r1, #4
 8005916:	6819      	ldr	r1, [r3, #0]
 8005918:	6820      	ldr	r0, [r4, #0]
 800591a:	4281      	cmp	r1, r0
 800591c:	d100      	bne.n	0x8005920
 800591e:	3501      	adds	r5, #1
 8005920:	341c      	adds	r4, #28
 8005922:	331c      	adds	r3, #28
 8005924:	3a01      	subs	r2, #1
 8005926:	2a00      	cmp	r2, #0
 8005928:	d1f5      	bne.n	0x8005916
 800592a:	7836      	ldrb	r6, [r6, #0]
 800592c:	42b5      	cmp	r5, r6
 800592e:	d007      	beq.n	0x8005940
 8005930:	2000      	movs	r0, #0
 8005932:	e006      	b.n	0x8005942
 8005934:	2ef4      	cmp	r6, #244	@ 0xf4
 8005936:	0300      	lsls	r0, r0, #12
 8005938:	28e0      	cmp	r0, #224	@ 0xe0
 800593a:	0300      	lsls	r0, r0, #12
 800593c:	2f40      	cmp	r7, #64	@ 0x40
 800593e:	0300      	lsls	r0, r0, #12
 8005940:	2001      	movs	r0, #1
 8005942:	bc70      	pop	{r4, r5, r6}
 8005944:	bc02      	pop	{r1}
 8005946:	4708      	bx	r1
 8005948:	b5f0      	push	{r4, r5, r6, r7, lr}
 800594a:	4647      	mov	r7, r8
 800594c:	b480      	push	{r7}
 800594e:	2400      	movs	r4, #0
 8005950:	4818      	ldr	r0, [pc, #96]	@ (0x80059b4)
 8005952:	7800      	ldrb	r0, [r0, #0]
 8005954:	4284      	cmp	r4, r0
 8005956:	d227      	bcs.n	0x80059a8
 8005958:	4e17      	ldr	r6, [pc, #92]	@ (0x80059b8)
 800595a:	4d18      	ldr	r5, [pc, #96]	@ (0x80059bc)
 800595c:	2008      	movs	r0, #8
 800595e:	1980      	adds	r0, r0, r6
 8005960:	4680      	mov	r8, r0
 8005962:	1c2f      	adds	r7, r5, #0
 8005964:	3708      	adds	r7, #8
 8005966:	00e0      	lsls	r0, r4, #3
 8005968:	1b00      	subs	r0, r0, r4
 800596a:	0082      	lsls	r2, r0, #2
 800596c:	1d31      	adds	r1, r6, #4
 800596e:	1851      	adds	r1, r2, r1
 8005970:	1d28      	adds	r0, r5, #4
 8005972:	1810      	adds	r0, r2, r0
 8005974:	6809      	ldr	r1, [r1, #0]
 8005976:	6800      	ldr	r0, [r0, #0]
 8005978:	4281      	cmp	r1, r0
 800597a:	d106      	bne.n	0x800598a
 800597c:	4641      	mov	r1, r8
 800597e:	1850      	adds	r0, r2, r1
 8005980:	19d1      	adds	r1, r2, r7
 8005982:	f7fe fd03 	bl	0x800438c
 8005986:	2800      	cmp	r0, #0
 8005988:	d007      	beq.n	0x800599a
 800598a:	490d      	ldr	r1, [pc, #52]	@ (0x80059c0)
 800598c:	2001      	movs	r0, #1
 800598e:	7008      	strb	r0, [r1, #0]
 8005990:	f7ff f8b6 	bl	0x8004b00
 8005994:	480b      	ldr	r0, [pc, #44]	@ (0x80059c4)
 8005996:	f7fa fd1d 	bl	0x80003d4
 800599a:	1c60      	adds	r0, r4, #1
 800599c:	0600      	lsls	r0, r0, #24
 800599e:	0e04      	lsrs	r4, r0, #24
 80059a0:	4804      	ldr	r0, [pc, #16]	@ (0x80059b4)
 80059a2:	7800      	ldrb	r0, [r0, #0]
 80059a4:	4284      	cmp	r4, r0
 80059a6:	d3de      	bcc.n	0x8005966
 80059a8:	bc08      	pop	{r3}
 80059aa:	4698      	mov	r8, r3
 80059ac:	bcf0      	pop	{r4, r5, r6, r7}
 80059ae:	bc01      	pop	{r0}
 80059b0:	4700      	bx	r0
 80059b2:	0000      	movs	r0, r0
 80059b4:	2ef4      	cmp	r6, #244	@ 0xf4
 80059b6:	0300      	lsls	r0, r0, #12
 80059b8:	2f40      	cmp	r7, #64	@ 0x40
 80059ba:	0300      	lsls	r0, r0, #12
 80059bc:	28e0      	cmp	r0, #224	@ 0xe0
 80059be:	0300      	lsls	r0, r0, #12
 80059c0:	28cc      	cmp	r0, #204	@ 0xcc
 80059c2:	0300      	lsls	r0, r0, #12
 80059c4:	5bd5      	ldrh	r5, [r2, r7]
 80059c6:	0800      	lsrs	r0, r0, #32
 80059c8:	4802      	ldr	r0, [pc, #8]	@ (0x80059d4)
 80059ca:	2100      	movs	r1, #0
 80059cc:	7001      	strb	r1, [r0, #0]
 80059ce:	4802      	ldr	r0, [pc, #8]	@ (0x80059d8)
 80059d0:	7001      	strb	r1, [r0, #0]
 80059d2:	4770      	bx	lr
 80059d4:	2ef4      	cmp	r6, #244	@ 0xf4
 80059d6:	0300      	lsls	r0, r0, #12
 80059d8:	2f10      	cmp	r7, #16
 80059da:	0300      	lsls	r0, r0, #12
 80059dc:	4802      	ldr	r0, [pc, #8]	@ (0x80059e8)
 80059de:	6800      	ldr	r0, [r0, #0]
 80059e0:	211c      	movs	r1, #28
 80059e2:	4008      	ands	r0, r1
 80059e4:	0880      	lsrs	r0, r0, #2
 80059e6:	4770      	bx	lr
 80059e8:	29d0      	cmp	r1, #208	@ 0xd0
 80059ea:	0300      	lsls	r0, r0, #12
 80059ec:	4802      	ldr	r0, [pc, #8]	@ (0x80059f8)
 80059ee:	6800      	ldr	r0, [r0, #0]
 80059f0:	0940      	lsrs	r0, r0, #5
 80059f2:	2101      	movs	r1, #1
 80059f4:	4008      	ands	r0, r1
 80059f6:	4770      	bx	lr
 80059f8:	29d0      	cmp	r1, #208	@ 0xd0
 80059fa:	0300      	lsls	r0, r0, #12
 80059fc:	4801      	ldr	r0, [pc, #4]	@ (0x8005a04)
 80059fe:	7800      	ldrb	r0, [r0, #0]
 8005a00:	4770      	bx	lr
 8005a02:	0000      	movs	r0, r0
 8005a04:	0398      	lsls	r0, r3, #14
 8005a06:	0300      	lsls	r0, r0, #12
 8005a08:	b500      	push	{lr}
 8005a0a:	4a05      	ldr	r2, [pc, #20]	@ (0x8005a20)
 8005a0c:	6811      	ldr	r1, [r2, #0]
 8005a0e:	2900      	cmp	r1, #0
 8005a10:	d103      	bne.n	0x8005a1a
 8005a12:	4804      	ldr	r0, [pc, #16]	@ (0x8005a24)
 8005a14:	6010      	str	r0, [r2, #0]
 8005a16:	4804      	ldr	r0, [pc, #16]	@ (0x8005a28)
 8005a18:	7001      	strb	r1, [r0, #0]
 8005a1a:	bc01      	pop	{r0}
 8005a1c:	4700      	bx	r0
 8005a1e:	0000      	movs	r0, r0
 8005a20:	2f30      	cmp	r7, #48	@ 0x30
 8005a22:	0300      	lsls	r0, r0, #12
 8005a24:	5a2d      	ldrh	r5, [r5, r0]
 8005a26:	0800      	lsrs	r0, r0, #32
 8005a28:	29d4      	cmp	r1, #212	@ 0xd4
 8005a2a:	0300      	lsls	r0, r0, #12
 8005a2c:	b500      	push	{lr}
 8005a2e:	4806      	ldr	r0, [pc, #24]	@ (0x8005a48)
 8005a30:	7800      	ldrb	r0, [r0, #0]
 8005a32:	2800      	cmp	r0, #0
 8005a34:	d105      	bne.n	0x8005a42
 8005a36:	4805      	ldr	r0, [pc, #20]	@ (0x8005a4c)
 8005a38:	f7ff fb24 	bl	0x8005084
 8005a3c:	4904      	ldr	r1, [pc, #16]	@ (0x8005a50)
 8005a3e:	4805      	ldr	r0, [pc, #20]	@ (0x8005a54)
 8005a40:	6008      	str	r0, [r1, #0]
 8005a42:	bc01      	pop	{r0}
 8005a44:	4700      	bx	r0
 8005a46:	0000      	movs	r0, r0
 8005a48:	3fa0      	subs	r7, #160	@ 0xa0
 8005a4a:	0300      	lsls	r0, r0, #12
 8005a4c:	5fff      	ldrsh	r7, [r7, r7]
 8005a4e:	0000      	movs	r0, r0
 8005a50:	2f30      	cmp	r7, #48	@ 0x30
 8005a52:	0300      	lsls	r0, r0, #12
 8005a54:	5a59      	ldrh	r1, [r3, r1]
 8005a56:	0800      	lsrs	r0, r0, #32
 8005a58:	b510      	push	{r4, lr}
 8005a5a:	f7ff fbfb 	bl	0x8005254
 8005a5e:	0600      	lsls	r0, r0, #24
 8005a60:	0e02      	lsrs	r2, r0, #24
 8005a62:	2300      	movs	r3, #0
 8005a64:	2100      	movs	r1, #0
 8005a66:	4293      	cmp	r3, r2
 8005a68:	da08      	bge.n	0x8005a7c
 8005a6a:	4c0e      	ldr	r4, [pc, #56]	@ (0x8005aa4)
 8005a6c:	1908      	adds	r0, r1, r4
 8005a6e:	7800      	ldrb	r0, [r0, #0]
 8005a70:	2800      	cmp	r0, #0
 8005a72:	d000      	beq.n	0x8005a76
 8005a74:	3301      	adds	r3, #1
 8005a76:	3101      	adds	r1, #1
 8005a78:	4291      	cmp	r1, r2
 8005a7a:	dbf7      	blt.n	0x8005a6c
 8005a7c:	4293      	cmp	r3, r2
 8005a7e:	d10e      	bne.n	0x8005a9e
 8005a80:	4a09      	ldr	r2, [pc, #36]	@ (0x8005aa8)
 8005a82:	8811      	ldrh	r1, [r2, #0]
 8005a84:	4809      	ldr	r0, [pc, #36]	@ (0x8005aac)
 8005a86:	4008      	ands	r0, r1
 8005a88:	8010      	strh	r0, [r2, #0]
 8005a8a:	4809      	ldr	r0, [pc, #36]	@ (0x8005ab0)
 8005a8c:	2401      	movs	r4, #1
 8005a8e:	7004      	strb	r4, [r0, #0]
 8005a90:	f7ff f836 	bl	0x8004b00
 8005a94:	4907      	ldr	r1, [pc, #28]	@ (0x8005ab4)
 8005a96:	2000      	movs	r0, #0
 8005a98:	6008      	str	r0, [r1, #0]
 8005a9a:	4807      	ldr	r0, [pc, #28]	@ (0x8005ab8)
 8005a9c:	7004      	strb	r4, [r0, #0]
 8005a9e:	bc10      	pop	{r4}
 8005aa0:	bc01      	pop	{r0}
 8005aa2:	4700      	bx	r0
 8005aa4:	2ae8      	cmp	r2, #232	@ 0xe8
 8005aa6:	0300      	lsls	r0, r0, #12
 8005aa8:	3758      	adds	r7, #88	@ 0x58
 8005aaa:	0202      	lsls	r2, r0, #8
 8005aac:	ffdf 0000 	vaddl.u16	q8, d15, d0
 8005ab0:	1b68      	subs	r0, r5, r5
 8005ab2:	0300      	lsls	r0, r0, #12
 8005ab4:	2f30      	cmp	r7, #48	@ 0x30
 8005ab6:	0300      	lsls	r0, r0, #12
 8005ab8:	29d4      	cmp	r1, #212	@ 0xd4
 8005aba:	0300      	lsls	r0, r0, #12
 8005abc:	b500      	push	{lr}
 8005abe:	4905      	ldr	r1, [pc, #20]	@ (0x8005ad4)
 8005ac0:	6808      	ldr	r0, [r1, #0]
 8005ac2:	2800      	cmp	r0, #0
 8005ac4:	d101      	bne.n	0x8005aca
 8005ac6:	4804      	ldr	r0, [pc, #16]	@ (0x8005ad8)
 8005ac8:	6008      	str	r0, [r1, #0]
 8005aca:	4904      	ldr	r1, [pc, #16]	@ (0x8005adc)
 8005acc:	2000      	movs	r0, #0
 8005ace:	7008      	strb	r0, [r1, #0]
 8005ad0:	bc01      	pop	{r0}
 8005ad2:	4700      	bx	r0
 8005ad4:	2f30      	cmp	r7, #48	@ 0x30
 8005ad6:	0300      	lsls	r0, r0, #12
 8005ad8:	5ae1      	ldrh	r1, [r4, r3]
 8005ada:	0800      	lsrs	r0, r0, #32
 8005adc:	29d4      	cmp	r1, #212	@ 0xd4
 8005ade:	0300      	lsls	r0, r0, #12
 8005ae0:	b500      	push	{lr}
 8005ae2:	4806      	ldr	r0, [pc, #24]	@ (0x8005afc)
 8005ae4:	7800      	ldrb	r0, [r0, #0]
 8005ae6:	2800      	cmp	r0, #0
 8005ae8:	d105      	bne.n	0x8005af6
 8005aea:	4805      	ldr	r0, [pc, #20]	@ (0x8005b00)
 8005aec:	f7ff faca 	bl	0x8005084
 8005af0:	4904      	ldr	r1, [pc, #16]	@ (0x8005b04)
 8005af2:	4805      	ldr	r0, [pc, #20]	@ (0x8005b08)
 8005af4:	6008      	str	r0, [r1, #0]
 8005af6:	bc01      	pop	{r0}
 8005af8:	4700      	bx	r0
 8005afa:	0000      	movs	r0, r0
 8005afc:	3fa0      	subs	r7, #160	@ 0xa0
 8005afe:	0300      	lsls	r0, r0, #12
 8005b00:	2ffe      	cmp	r7, #254	@ 0xfe
 8005b02:	0000      	movs	r0, r0
 8005b04:	2f30      	cmp	r7, #48	@ 0x30
 8005b06:	0300      	lsls	r0, r0, #12
 8005b08:	5b0d      	ldrh	r5, [r1, r4]
 8005b0a:	0800      	lsrs	r0, r0, #32
 8005b0c:	b510      	push	{r4, lr}
 8005b0e:	f7ff fba1 	bl	0x8005254
 8005b12:	0600      	lsls	r0, r0, #24
 8005b14:	0e02      	lsrs	r2, r0, #24
 8005b16:	2100      	movs	r1, #0
 8005b18:	4291      	cmp	r1, r2
 8005b1a:	d20c      	bcs.n	0x8005b36
 8005b1c:	4b0f      	ldr	r3, [pc, #60]	@ (0x8005b5c)
 8005b1e:	7818      	ldrb	r0, [r3, #0]
 8005b20:	2800      	cmp	r0, #0
 8005b22:	d008      	beq.n	0x8005b36
 8005b24:	1c48      	adds	r0, r1, #1
 8005b26:	0600      	lsls	r0, r0, #24
 8005b28:	0e01      	lsrs	r1, r0, #24
 8005b2a:	4291      	cmp	r1, r2
 8005b2c:	d203      	bcs.n	0x8005b36
 8005b2e:	18c8      	adds	r0, r1, r3
 8005b30:	7800      	ldrb	r0, [r0, #0]
 8005b32:	2800      	cmp	r0, #0
 8005b34:	d1f6      	bne.n	0x8005b24
 8005b36:	4291      	cmp	r1, r2
 8005b38:	d10c      	bne.n	0x8005b54
 8005b3a:	2100      	movs	r1, #0
 8005b3c:	4c08      	ldr	r4, [pc, #32]	@ (0x8005b60)
 8005b3e:	4b07      	ldr	r3, [pc, #28]	@ (0x8005b5c)
 8005b40:	2200      	movs	r2, #0
 8005b42:	18c8      	adds	r0, r1, r3
 8005b44:	7002      	strb	r2, [r0, #0]
 8005b46:	1c48      	adds	r0, r1, #1
 8005b48:	0600      	lsls	r0, r0, #24
 8005b4a:	0e01      	lsrs	r1, r0, #24
 8005b4c:	2903      	cmp	r1, #3
 8005b4e:	d9f8      	bls.n	0x8005b42
 8005b50:	2000      	movs	r0, #0
 8005b52:	6020      	str	r0, [r4, #0]
 8005b54:	bc10      	pop	{r4}
 8005b56:	bc01      	pop	{r0}
 8005b58:	4700      	bx	r0
 8005b5a:	0000      	movs	r0, r0
 8005b5c:	2ae0      	cmp	r2, #224	@ 0xe0
 8005b5e:	0300      	lsls	r0, r0, #12
 8005b60:	2f30      	cmp	r7, #48	@ 0x30
 8005b62:	0300      	lsls	r0, r0, #12
 8005b64:	b500      	push	{lr}
 8005b66:	4811      	ldr	r0, [pc, #68]	@ (0x8005bac)
 8005b68:	7800      	ldrb	r0, [r0, #0]
 8005b6a:	2800      	cmp	r0, #0
 8005b6c:	d01c      	beq.n	0x8005ba8
 8005b6e:	4810      	ldr	r0, [pc, #64]	@ (0x8005bb0)
 8005b70:	6801      	ldr	r1, [r0, #0]
 8005b72:	20fe      	movs	r0, #254	@ 0xfe
 8005b74:	02c0      	lsls	r0, r0, #11
 8005b76:	4008      	ands	r0, r1
 8005b78:	2800      	cmp	r0, #0
 8005b7a:	d015      	beq.n	0x8005ba8
 8005b7c:	480d      	ldr	r0, [pc, #52]	@ (0x8005bb4)
 8005b7e:	7800      	ldrb	r0, [r0, #0]
 8005b80:	2800      	cmp	r0, #0
 8005b82:	d10c      	bne.n	0x8005b9e
 8005b84:	480c      	ldr	r0, [pc, #48]	@ (0x8005bb8)
 8005b86:	6001      	str	r1, [r0, #0]
 8005b88:	490c      	ldr	r1, [pc, #48]	@ (0x8005bbc)
 8005b8a:	480d      	ldr	r0, [pc, #52]	@ (0x8005bc0)
 8005b8c:	7800      	ldrb	r0, [r0, #0]
 8005b8e:	6008      	str	r0, [r1, #0]
 8005b90:	490c      	ldr	r1, [pc, #48]	@ (0x8005bc4)
 8005b92:	480d      	ldr	r0, [pc, #52]	@ (0x8005bc8)
 8005b94:	7800      	ldrb	r0, [r0, #0]
 8005b96:	6008      	str	r0, [r1, #0]
 8005b98:	480c      	ldr	r0, [pc, #48]	@ (0x8005bcc)
 8005b9a:	f7fa fc1b 	bl	0x80003d4
 8005b9e:	490c      	ldr	r1, [pc, #48]	@ (0x8005bd0)
 8005ba0:	2001      	movs	r0, #1
 8005ba2:	7008      	strb	r0, [r1, #0]
 8005ba4:	f7fe ffac 	bl	0x8004b00
 8005ba8:	bc01      	pop	{r0}
 8005baa:	4700      	bx	r0
 8005bac:	3620      	adds	r6, #32
 8005bae:	0202      	lsls	r2, r0, #8
 8005bb0:	29d0      	cmp	r1, #208	@ 0xd0
 8005bb2:	0300      	lsls	r0, r0, #12
 8005bb4:	2ef0      	cmp	r6, #240	@ 0xf0
 8005bb6:	0300      	lsls	r0, r0, #12
 8005bb8:	03a0      	lsls	r0, r4, #14
 8005bba:	0300      	lsls	r0, r0, #12
 8005bbc:	03a4      	lsls	r4, r4, #14
 8005bbe:	0300      	lsls	r0, r0, #12
 8005bc0:	3fa0      	subs	r7, #160	@ 0xa0
 8005bc2:	0300      	lsls	r0, r0, #12
 8005bc4:	03a8      	lsls	r0, r5, #14
 8005bc6:	0300      	lsls	r0, r0, #12
 8005bc8:	2fd0      	cmp	r7, #208	@ 0xd0
 8005bca:	0300      	lsls	r0, r0, #12
 8005bcc:	5bd5      	ldrh	r5, [r2, r7]
 8005bce:	0800      	lsrs	r0, r0, #32
 8005bd0:	28cc      	cmp	r0, #204	@ 0xcc
 8005bd2:	0300      	lsls	r0, r0, #12
 8005bd4:	b500      	push	{lr}
 8005bd6:	f7fa fdb9 	bl	0x800074c
 8005bda:	f7fc fbfd 	bl	0x80023d8
 8005bde:	f06b faa3 	bl	0x8071128
 8005be2:	2000      	movs	r0, #0
 8005be4:	2100      	movs	r1, #0
 8005be6:	2202      	movs	r2, #2
 8005be8:	f06a ff6e 	bl	0x8070ac8
 8005bec:	f071 ff3a 	bl	0x8077a64
 8005bf0:	4816      	ldr	r0, [pc, #88]	@ (0x8005c4c)
 8005bf2:	f7fa fca7 	bl	0x8000544
 8005bf6:	2006      	movs	r0, #6
 8005bf8:	f7fc fdf0 	bl	0x80027dc
 8005bfc:	2006      	movs	r0, #6
 8005bfe:	f069 f9bb 	bl	0x806ef78
 8005c02:	f069 fb05 	bl	0x806f210
 8005c06:	4812      	ldr	r0, [pc, #72]	@ (0x8005c50)
 8005c08:	2100      	movs	r1, #0
 8005c0a:	8001      	strh	r1, [r0, #0]
 8005c0c:	3840      	subs	r0, #64	@ 0x40
 8005c0e:	8001      	strh	r1, [r0, #0]
 8005c10:	3802      	subs	r0, #2
 8005c12:	8001      	strh	r1, [r0, #0]
 8005c14:	2280      	movs	r2, #128	@ 0x80
 8005c16:	04d2      	lsls	r2, r2, #19
 8005c18:	23a0      	movs	r3, #160	@ 0xa0
 8005c1a:	005b      	lsls	r3, r3, #1
 8005c1c:	1c18      	adds	r0, r3, #0
 8005c1e:	8010      	strh	r0, [r2, #0]
 8005c20:	480c      	ldr	r0, [pc, #48]	@ (0x8005c54)
 8005c22:	7001      	strb	r1, [r0, #0]
 8005c24:	480c      	ldr	r0, [pc, #48]	@ (0x8005c58)
 8005c26:	2100      	movs	r1, #0
 8005c28:	f071 ff4c 	bl	0x8077ac4
 8005c2c:	f06c f888 	bl	0x8071d40
 8005c30:	f071 fff6 	bl	0x8077c20
 8005c34:	f7fa fdb0 	bl	0x8000798
 8005c38:	f7fa fdd4 	bl	0x80007e4
 8005c3c:	f06a ff9a 	bl	0x8070b74
 8005c40:	4806      	ldr	r0, [pc, #24]	@ (0x8005c5c)
 8005c42:	f7fa fbc7 	bl	0x80003d4
 8005c46:	bc01      	pop	{r0}
 8005c48:	4700      	bx	r0
 8005c4a:	0000      	movs	r0, r0
 8005c4c:	4a01      	ldr	r2, [pc, #4]	@ (0x8005c54)
 8005c4e:	0800      	lsrs	r0, r0, #32
 8005c50:	0052      	lsls	r2, r2, #1
 8005c52:	0400      	lsls	r0, r0, #16
 8005c54:	1b20      	subs	r0, r4, r4
 8005c56:	0300      	lsls	r0, r0, #12
 8005c58:	4789      			@ <UNDEFINED> instruction: 0x4789
 8005c5a:	0800      	lsrs	r0, r0, #32
 8005c5c:	5c61      	ldrb	r1, [r4, r1]
 8005c5e:	0800      	lsrs	r0, r0, #32
 8005c60:	b500      	push	{lr}
 8005c62:	b090      	sub	sp, #64	@ 0x40
 8005c64:	4805      	ldr	r0, [pc, #20]	@ (0x8005c7c)
 8005c66:	2187      	movs	r1, #135	@ 0x87
 8005c68:	00c9      	lsls	r1, r1, #3
 8005c6a:	1840      	adds	r0, r0, r1
 8005c6c:	7800      	ldrb	r0, [r0, #0]
 8005c6e:	281e      	cmp	r0, #30
 8005c70:	d014      	beq.n	0x8005c9c
 8005c72:	281e      	cmp	r0, #30
 8005c74:	dc04      	bgt.n	0x8005c80
 8005c76:	2800      	cmp	r0, #0
 8005c78:	d007      	beq.n	0x8005c8a
 8005c7a:	e016      	b.n	0x8005caa
 8005c7c:	16e0      	asrs	r0, r4, #27
 8005c7e:	0300      	lsls	r0, r0, #12
 8005c80:	283c      	cmp	r0, #60	@ 0x3c
 8005c82:	d00b      	beq.n	0x8005c9c
 8005c84:	285a      	cmp	r0, #90	@ 0x5a
 8005c86:	d00d      	beq.n	0x8005ca4
 8005c88:	e00f      	b.n	0x8005caa
 8005c8a:	4803      	ldr	r0, [pc, #12]	@ (0x8005c98)
 8005c8c:	2107      	movs	r1, #7
 8005c8e:	2207      	movs	r2, #7
 8005c90:	f069 fa6c 	bl	0x806f16c
 8005c94:	e009      	b.n	0x8005caa
 8005c96:	0000      	movs	r0, r0
 8005c98:	bd94      	pop	{r2, r4, r7, pc}
 8005c9a:	081b      	lsrs	r3, r3, #32
 8005c9c:	2016      	movs	r0, #22
 8005c9e:	f06c fc15 	bl	0x80724cc
 8005ca2:	e002      	b.n	0x8005caa
 8005ca4:	2016      	movs	r0, #22
 8005ca6:	f06c fc11 	bl	0x80724cc
 8005caa:	4806      	ldr	r0, [pc, #24]	@ (0x8005cc4)
 8005cac:	2287      	movs	r2, #135	@ 0x87
 8005cae:	00d2      	lsls	r2, r2, #3
 8005cb0:	1881      	adds	r1, r0, r2
 8005cb2:	7808      	ldrb	r0, [r1, #0]
 8005cb4:	28c8      	cmp	r0, #200	@ 0xc8
 8005cb6:	d001      	beq.n	0x8005cbc
 8005cb8:	3001      	adds	r0, #1
 8005cba:	7008      	strb	r0, [r1, #0]
 8005cbc:	b010      	add	sp, #64	@ 0x40
 8005cbe:	bc01      	pop	{r0}
 8005cc0:	4700      	bx	r0
 8005cc2:	0000      	movs	r0, r0
 8005cc4:	16e0      	asrs	r0, r4, #27
 8005cc6:	0300      	lsls	r0, r0, #12
 8005cc8:	4802      	ldr	r0, [pc, #8]	@ (0x8005cd4)
 8005cca:	8800      	ldrh	r0, [r0, #0]
 8005ccc:	0880      	lsrs	r0, r0, #2
 8005cce:	2101      	movs	r1, #1
 8005cd0:	4008      	ands	r0, r1
 8005cd2:	4770      	bx	lr
 8005cd4:	0128      	lsls	r0, r5, #4
 8005cd6:	0400      	lsls	r0, r0, #16
 8005cd8:	b500      	push	{lr}
 8005cda:	2300      	movs	r3, #0
 8005cdc:	4a07      	ldr	r2, [pc, #28]	@ (0x8005cfc)
 8005cde:	8811      	ldrh	r1, [r2, #0]
 8005ce0:	2008      	movs	r0, #8
 8005ce2:	4008      	ands	r0, r1
 8005ce4:	2800      	cmp	r0, #0
 8005ce6:	d005      	beq.n	0x8005cf4
 8005ce8:	8811      	ldrh	r1, [r2, #0]
 8005cea:	2004      	movs	r0, #4
 8005cec:	4008      	ands	r0, r1
 8005cee:	2800      	cmp	r0, #0
 8005cf0:	d100      	bne.n	0x8005cf4
 8005cf2:	2301      	movs	r3, #1
 8005cf4:	1c18      	adds	r0, r3, #0
 8005cf6:	bc02      	pop	{r1}
 8005cf8:	4708      	bx	r1
 8005cfa:	0000      	movs	r0, r0
 8005cfc:	0128      	lsls	r0, r5, #4
 8005cfe:	0400      	lsls	r0, r0, #16
 8005d00:	4802      	ldr	r0, [pc, #8]	@ (0x8005d0c)
 8005d02:	6800      	ldr	r0, [r0, #0]
 8005d04:	0980      	lsrs	r0, r0, #6
 8005d06:	2101      	movs	r1, #1
 8005d08:	4008      	ands	r0, r1
 8005d0a:	4770      	bx	lr
 8005d0c:	29d0      	cmp	r1, #208	@ 0xd0
 8005d0e:	0300      	lsls	r0, r0, #12
 8005d10:	4901      	ldr	r1, [pc, #4]	@ (0x8005d18)
 8005d12:	7008      	strb	r0, [r1, #0]
 8005d14:	4770      	bx	lr
 8005d16:	0000      	movs	r0, r0
 8005d18:	2ef0      	cmp	r6, #240	@ 0xf0
 8005d1a:	0300      	lsls	r0, r0, #12
 8005d1c:	4801      	ldr	r0, [pc, #4]	@ (0x8005d24)
 8005d1e:	7800      	ldrb	r0, [r0, #0]
 8005d20:	4770      	bx	lr
 8005d22:	0000      	movs	r0, r0
 8005d24:	28cc      	cmp	r0, #204	@ 0xcc
 8005d26:	0300      	lsls	r0, r0, #12
 8005d28:	b530      	push	{r4, r5, lr}
 8005d2a:	b081      	sub	sp, #4
 8005d2c:	480e      	ldr	r0, [pc, #56]	@ (0x8005d68)
 8005d2e:	4a0f      	ldr	r2, [pc, #60]	@ (0x8005d6c)
 8005d30:	8815      	ldrh	r5, [r2, #0]
 8005d32:	8005      	strh	r5, [r0, #0]
 8005d34:	2400      	movs	r4, #0
 8005d36:	8014      	strh	r4, [r2, #0]
 8005d38:	4b0d      	ldr	r3, [pc, #52]	@ (0x8005d70)
 8005d3a:	8819      	ldrh	r1, [r3, #0]
 8005d3c:	480d      	ldr	r0, [pc, #52]	@ (0x8005d74)
 8005d3e:	4008      	ands	r0, r1
 8005d40:	8018      	strh	r0, [r3, #0]
 8005d42:	8015      	strh	r5, [r2, #0]
 8005d44:	480c      	ldr	r0, [pc, #48]	@ (0x8005d78)
 8005d46:	8004      	strh	r4, [r0, #0]
 8005d48:	381a      	subs	r0, #26
 8005d4a:	8004      	strh	r4, [r0, #0]
 8005d4c:	490b      	ldr	r1, [pc, #44]	@ (0x8005d7c)
 8005d4e:	20c0      	movs	r0, #192	@ 0xc0
 8005d50:	8008      	strh	r0, [r1, #0]
 8005d52:	2000      	movs	r0, #0
 8005d54:	9000      	str	r0, [sp, #0]
 8005d56:	490a      	ldr	r1, [pc, #40]	@ (0x8005d80)
 8005d58:	4a0a      	ldr	r2, [pc, #40]	@ (0x8005d84)
 8005d5a:	4668      	mov	r0, sp
 8005d5c:	f1ab fa9a 	bl	0x81b1294
 8005d60:	b001      	add	sp, #4
 8005d62:	bc30      	pop	{r4, r5}
 8005d64:	bc01      	pop	{r0}
 8005d66:	4700      	bx	r0
 8005d68:	3fa4      	subs	r7, #164	@ 0xa4
 8005d6a:	0300      	lsls	r0, r0, #12
 8005d6c:	0208      	lsls	r0, r1, #8
 8005d6e:	0400      	lsls	r0, r0, #16
 8005d70:	0200      	lsls	r0, r0, #8
 8005d72:	0400      	lsls	r0, r0, #16
 8005d74:	ff3f 0000 	vhadd.u<illegal width 64>	d0, d15, d0
 8005d78:	0128      	lsls	r0, r5, #4
 8005d7a:	0400      	lsls	r0, r0, #16
 8005d7c:	0202      	lsls	r2, r0, #8
 8005d7e:	0400      	lsls	r0, r0, #16
 8005d80:	2fe0      	cmp	r7, #224	@ 0xe0
 8005d82:	0300      	lsls	r0, r0, #12
 8005d84:	03f0      	lsls	r0, r6, #15
 8005d86:	0500      	lsls	r0, r0, #20
 8005d88:	b5f0      	push	{r4, r5, r6, r7, lr}
 8005d8a:	b081      	sub	sp, #4
 8005d8c:	4e1c      	ldr	r6, [pc, #112]	@ (0x8005e00)
 8005d8e:	4b1d      	ldr	r3, [pc, #116]	@ (0x8005e04)
 8005d90:	881a      	ldrh	r2, [r3, #0]
 8005d92:	2400      	movs	r4, #0
 8005d94:	801c      	strh	r4, [r3, #0]
 8005d96:	4d1c      	ldr	r5, [pc, #112]	@ (0x8005e08)
 8005d98:	8829      	ldrh	r1, [r5, #0]
 8005d9a:	481c      	ldr	r0, [pc, #112]	@ (0x8005e0c)
 8005d9c:	4008      	ands	r0, r1
 8005d9e:	8028      	strh	r0, [r5, #0]
 8005da0:	801a      	strh	r2, [r3, #0]
 8005da2:	481b      	ldr	r0, [pc, #108]	@ (0x8005e10)
 8005da4:	8004      	strh	r4, [r0, #0]
 8005da6:	4a1b      	ldr	r2, [pc, #108]	@ (0x8005e14)
 8005da8:	2180      	movs	r1, #128	@ 0x80
 8005daa:	0189      	lsls	r1, r1, #6
 8005dac:	1c08      	adds	r0, r1, #0
 8005dae:	8010      	strh	r0, [r2, #0]
 8005db0:	8810      	ldrh	r0, [r2, #0]
 8005db2:	4f19      	ldr	r7, [pc, #100]	@ (0x8005e18)
 8005db4:	1c39      	adds	r1, r7, #0
 8005db6:	4308      	orrs	r0, r1
 8005db8:	8010      	strh	r0, [r2, #0]
 8005dba:	881a      	ldrh	r2, [r3, #0]
 8005dbc:	8032      	strh	r2, [r6, #0]
 8005dbe:	801c      	strh	r4, [r3, #0]
 8005dc0:	8828      	ldrh	r0, [r5, #0]
 8005dc2:	2180      	movs	r1, #128	@ 0x80
 8005dc4:	4308      	orrs	r0, r1
 8005dc6:	8028      	strh	r0, [r5, #0]
 8005dc8:	801a      	strh	r2, [r3, #0]
 8005dca:	4814      	ldr	r0, [pc, #80]	@ (0x8005e1c)
 8005dcc:	8004      	strh	r4, [r0, #0]
 8005dce:	2500      	movs	r5, #0
 8005dd0:	9500      	str	r5, [sp, #0]
 8005dd2:	4913      	ldr	r1, [pc, #76]	@ (0x8005e20)
 8005dd4:	4a13      	ldr	r2, [pc, #76]	@ (0x8005e24)
 8005dd6:	4668      	mov	r0, sp
 8005dd8:	f1ab fa5c 	bl	0x81b1294
 8005ddc:	4812      	ldr	r0, [pc, #72]	@ (0x8005e28)
 8005dde:	7004      	strb	r4, [r0, #0]
 8005de0:	4812      	ldr	r0, [pc, #72]	@ (0x8005e2c)
 8005de2:	8005      	strh	r5, [r0, #0]
 8005de4:	4812      	ldr	r0, [pc, #72]	@ (0x8005e30)
 8005de6:	8005      	strh	r5, [r0, #0]
 8005de8:	4812      	ldr	r0, [pc, #72]	@ (0x8005e34)
 8005dea:	7004      	strb	r4, [r0, #0]
 8005dec:	4812      	ldr	r0, [pc, #72]	@ (0x8005e38)
 8005dee:	7004      	strb	r4, [r0, #0]
 8005df0:	4812      	ldr	r0, [pc, #72]	@ (0x8005e3c)
 8005df2:	7004      	strb	r4, [r0, #0]
 8005df4:	4812      	ldr	r0, [pc, #72]	@ (0x8005e40)
 8005df6:	7004      	strb	r4, [r0, #0]
 8005df8:	b001      	add	sp, #4
 8005dfa:	bcf0      	pop	{r4, r5, r6, r7}
 8005dfc:	bc01      	pop	{r0}
 8005dfe:	4700      	bx	r0
 8005e00:	3fa4      	subs	r7, #164	@ 0xa4
 8005e02:	0300      	lsls	r0, r0, #12
 8005e04:	0208      	lsls	r0, r1, #8
 8005e06:	0400      	lsls	r0, r0, #16
 8005e08:	0200      	lsls	r0, r0, #8
 8005e0a:	0400      	lsls	r0, r0, #16
 8005e0c:	ff3f 0000 	vhadd.u<illegal width 64>	d0, d15, d0
 8005e10:	0134      	lsls	r4, r6, #4
 8005e12:	0400      	lsls	r0, r0, #16
 8005e14:	0128      	lsls	r0, r5, #4
 8005e16:	0400      	lsls	r0, r0, #16
 8005e18:	4003      	ands	r3, r0
 8005e1a:	0000      	movs	r0, r0
 8005e1c:	012a      	lsls	r2, r5, #4
 8005e1e:	0400      	lsls	r0, r0, #16
 8005e20:	2fe0      	cmp	r7, #224	@ 0xe0
 8005e22:	0300      	lsls	r0, r0, #12
 8005e24:	03f0      	lsls	r0, r6, #15
 8005e26:	0500      	lsls	r0, r0, #20
 8005e28:	03b8      	lsls	r0, r7, #14
 8005e2a:	0300      	lsls	r0, r0, #12
 8005e2c:	03ba      	lsls	r2, r7, #14
 8005e2e:	0300      	lsls	r0, r0, #12
 8005e30:	03bc      	lsls	r4, r7, #14
 8005e32:	0300      	lsls	r0, r0, #12
 8005e34:	03be      	lsls	r6, r7, #14
 8005e36:	0300      	lsls	r0, r0, #12
 8005e38:	03bf      	lsls	r7, r7, #14
 8005e3a:	0300      	lsls	r0, r0, #12
 8005e3c:	2fd0      	cmp	r7, #208	@ 0xd0
 8005e3e:	0300      	lsls	r0, r0, #12
 8005e40:	3fa0      	subs	r7, #160	@ 0xa0
 8005e42:	0300      	lsls	r0, r0, #12
 8005e44:	b500      	push	{lr}
 8005e46:	f7ff ff9f 	bl	0x8005d88
 8005e4a:	f7ff ff6d 	bl	0x8005d28
 8005e4e:	bc01      	pop	{r0}
 8005e50:	4700      	bx	r0
 8005e52:	0000      	movs	r0, r0
 8005e54:	b5f0      	push	{r4, r5, r6, r7, lr}
 8005e56:	1c04      	adds	r4, r0, #0
 8005e58:	1c0d      	adds	r5, r1, #0
 8005e5a:	1c16      	adds	r6, r2, #0
 8005e5c:	4804      	ldr	r0, [pc, #16]	@ (0x8005e70)
 8005e5e:	7840      	ldrb	r0, [r0, #1]
 8005e60:	2804      	cmp	r0, #4
 8005e62:	d850      	bhi.n	0x8005f06
 8005e64:	0080      	lsls	r0, r0, #2
 8005e66:	4903      	ldr	r1, [pc, #12]	@ (0x8005e74)
 8005e68:	1840      	adds	r0, r0, r1
 8005e6a:	6800      	ldr	r0, [r0, #0]
 8005e6c:	4687      	mov	pc, r0
 8005e6e:	0000      	movs	r0, r0
 8005e70:	2fe0      	cmp	r7, #224	@ 0xe0
 8005e72:	0300      	lsls	r0, r0, #12
 8005e74:	5e78      	ldrsh	r0, [r7, r1]
 8005e76:	0800      	lsrs	r0, r0, #32
 8005e78:	5e8c      	ldrsh	r4, [r1, r2]
 8005e7a:	0800      	lsrs	r0, r0, #32
 8005e7c:	5e9c      	ldrsh	r4, [r3, r2]
 8005e7e:	0800      	lsrs	r0, r0, #32
 8005e80:	5eb4      	ldrsh	r4, [r6, r2]
 8005e82:	0800      	lsrs	r0, r0, #32
 8005e84:	5ef0      	ldrsh	r0, [r6, r3]
 8005e86:	0800      	lsrs	r0, r0, #32
 8005e88:	5efa      	ldrsh	r2, [r7, r3]
 8005e8a:	0800      	lsrs	r0, r0, #32
 8005e8c:	f7ff ff4c 	bl	0x8005d28
 8005e90:	4901      	ldr	r1, [pc, #4]	@ (0x8005e98)
 8005e92:	2001      	movs	r0, #1
 8005e94:	7048      	strb	r0, [r1, #1]
 8005e96:	e036      	b.n	0x8005f06
 8005e98:	2fe0      	cmp	r7, #224	@ 0xe0
 8005e9a:	0300      	lsls	r0, r0, #12
 8005e9c:	7820      	ldrb	r0, [r4, #0]
 8005e9e:	2801      	cmp	r0, #1
 8005ea0:	d131      	bne.n	0x8005f06
 8005ea2:	f7ff ff71 	bl	0x8005d88
 8005ea6:	4902      	ldr	r1, [pc, #8]	@ (0x8005eb0)
 8005ea8:	2002      	movs	r0, #2
 8005eaa:	7048      	strb	r0, [r1, #1]
 8005eac:	e02b      	b.n	0x8005f06
 8005eae:	0000      	movs	r0, r0
 8005eb0:	2fe0      	cmp	r7, #224	@ 0xe0
 8005eb2:	0300      	lsls	r0, r0, #12
 8005eb4:	7821      	ldrb	r1, [r4, #0]
 8005eb6:	2901      	cmp	r1, #1
 8005eb8:	d004      	beq.n	0x8005ec4
 8005eba:	2902      	cmp	r1, #2
 8005ebc:	d00e      	beq.n	0x8005edc
 8005ebe:	f000 f85f 	bl	0x8005f80
 8005ec2:	e020      	b.n	0x8005f06
 8005ec4:	4a04      	ldr	r2, [pc, #16]	@ (0x8005ed8)
 8005ec6:	7810      	ldrb	r0, [r2, #0]
 8005ec8:	2808      	cmp	r0, #8
 8005eca:	d11c      	bne.n	0x8005f06
 8005ecc:	78d0      	ldrb	r0, [r2, #3]
 8005ece:	2801      	cmp	r0, #1
 8005ed0:	d919      	bls.n	0x8005f06
 8005ed2:	7391      	strb	r1, [r2, #14]
 8005ed4:	e017      	b.n	0x8005f06
 8005ed6:	0000      	movs	r0, r0
 8005ed8:	2fe0      	cmp	r7, #224	@ 0xe0
 8005eda:	0300      	lsls	r0, r0, #12
 8005edc:	4802      	ldr	r0, [pc, #8]	@ (0x8005ee8)
 8005ede:	2100      	movs	r1, #0
 8005ee0:	7041      	strb	r1, [r0, #1]
 8005ee2:	4802      	ldr	r0, [pc, #8]	@ (0x8005eec)
 8005ee4:	8001      	strh	r1, [r0, #0]
 8005ee6:	e00e      	b.n	0x8005f06
 8005ee8:	2fe0      	cmp	r7, #224	@ 0xe0
 8005eea:	0300      	lsls	r0, r0, #12
 8005eec:	012a      	lsls	r2, r5, #4
 8005eee:	0400      	lsls	r0, r0, #16
 8005ef0:	f000 f85c 	bl	0x8005fac
 8005ef4:	4912      	ldr	r1, [pc, #72]	@ (0x8005f40)
 8005ef6:	2004      	movs	r0, #4
 8005ef8:	7048      	strb	r0, [r1, #1]
 8005efa:	1c28      	adds	r0, r5, #0
 8005efc:	f000 f87e 	bl	0x8005ffc
 8005f00:	1c30      	adds	r0, r6, #0
 8005f02:	f000 f8ef 	bl	0x80060e4
 8005f06:	2000      	movs	r0, #0
 8005f08:	7020      	strb	r0, [r4, #0]
 8005f0a:	490d      	ldr	r1, [pc, #52]	@ (0x8005f40)
 8005f0c:	788a      	ldrb	r2, [r1, #2]
 8005f0e:	78c8      	ldrb	r0, [r1, #3]
 8005f10:	0080      	lsls	r0, r0, #2
 8005f12:	4302      	orrs	r2, r0
 8005f14:	7808      	ldrb	r0, [r1, #0]
 8005f16:	2808      	cmp	r0, #8
 8005f18:	d101      	bne.n	0x8005f1e
 8005f1a:	2020      	movs	r0, #32
 8005f1c:	4302      	orrs	r2, r0
 8005f1e:	7b08      	ldrb	r0, [r1, #12]
 8005f20:	0203      	lsls	r3, r0, #8
 8005f22:	7bc8      	ldrb	r0, [r1, #15]
 8005f24:	0244      	lsls	r4, r0, #9
 8005f26:	7c08      	ldrb	r0, [r1, #16]
 8005f28:	0305      	lsls	r5, r0, #12
 8005f2a:	7c48      	ldrb	r0, [r1, #17]
 8005f2c:	0346      	lsls	r6, r0, #13
 8005f2e:	7c88      	ldrb	r0, [r1, #18]
 8005f30:	0387      	lsls	r7, r0, #14
 8005f32:	7848      	ldrb	r0, [r1, #1]
 8005f34:	2804      	cmp	r0, #4
 8005f36:	d105      	bne.n	0x8005f44
 8005f38:	2040      	movs	r0, #64	@ 0x40
 8005f3a:	4318      	orrs	r0, r3
 8005f3c:	4310      	orrs	r0, r2
 8005f3e:	e003      	b.n	0x8005f48
 8005f40:	2fe0      	cmp	r7, #224	@ 0xe0
 8005f42:	0300      	lsls	r0, r0, #12
 8005f44:	1c10      	adds	r0, r2, #0
 8005f46:	4318      	orrs	r0, r3
 8005f48:	4320      	orrs	r0, r4
 8005f4a:	4328      	orrs	r0, r5
 8005f4c:	4330      	orrs	r0, r6
 8005f4e:	4338      	orrs	r0, r7
 8005f50:	1c02      	adds	r2, r0, #0
 8005f52:	7ccb      	ldrb	r3, [r1, #19]
 8005f54:	2b01      	cmp	r3, #1
 8005f56:	d102      	bne.n	0x8005f5e
 8005f58:	2080      	movs	r0, #128	@ 0x80
 8005f5a:	0240      	lsls	r0, r0, #9
 8005f5c:	4302      	orrs	r2, r0
 8005f5e:	7888      	ldrb	r0, [r1, #2]
 8005f60:	2803      	cmp	r0, #3
 8005f62:	d902      	bls.n	0x8005f6a
 8005f64:	2080      	movs	r0, #128	@ 0x80
 8005f66:	0280      	lsls	r0, r0, #10
 8005f68:	4302      	orrs	r2, r0
 8005f6a:	1c11      	adds	r1, r2, #0
 8005f6c:	2b02      	cmp	r3, #2
 8005f6e:	d102      	bne.n	0x8005f76
 8005f70:	2080      	movs	r0, #128	@ 0x80
 8005f72:	02c0      	lsls	r0, r0, #11
 8005f74:	4301      	orrs	r1, r0
 8005f76:	1c08      	adds	r0, r1, #0
 8005f78:	bcf0      	pop	{r4, r5, r6, r7}
 8005f7a:	bc02      	pop	{r1}
 8005f7c:	4708      	bx	r1
 8005f7e:	0000      	movs	r0, r0
 8005f80:	b500      	push	{lr}
 8005f82:	4806      	ldr	r0, [pc, #24]	@ (0x8005f9c)
 8005f84:	6801      	ldr	r1, [r0, #0]
 8005f86:	200c      	movs	r0, #12
 8005f88:	4001      	ands	r1, r0
 8005f8a:	4a05      	ldr	r2, [pc, #20]	@ (0x8005fa0)
 8005f8c:	2908      	cmp	r1, #8
 8005f8e:	d109      	bne.n	0x8005fa4
 8005f90:	7890      	ldrb	r0, [r2, #2]
 8005f92:	2800      	cmp	r0, #0
 8005f94:	d106      	bne.n	0x8005fa4
 8005f96:	7011      	strb	r1, [r2, #0]
 8005f98:	e006      	b.n	0x8005fa8
 8005f9a:	0000      	movs	r0, r0
 8005f9c:	0128      	lsls	r0, r5, #4
 8005f9e:	0400      	lsls	r0, r0, #16
 8005fa0:	2fe0      	cmp	r7, #224	@ 0xe0
 8005fa2:	0300      	lsls	r0, r0, #12
 8005fa4:	2000      	movs	r0, #0
 8005fa6:	7010      	strb	r0, [r2, #0]
 8005fa8:	bc01      	pop	{r0}
 8005faa:	4700      	bx	r0
 8005fac:	b510      	push	{r4, lr}
 8005fae:	480d      	ldr	r0, [pc, #52]	@ (0x8005fe4)
 8005fb0:	7800      	ldrb	r0, [r0, #0]
 8005fb2:	2800      	cmp	r0, #0
 8005fb4:	d012      	beq.n	0x8005fdc
 8005fb6:	490c      	ldr	r1, [pc, #48]	@ (0x8005fe8)
 8005fb8:	4a0c      	ldr	r2, [pc, #48]	@ (0x8005fec)
 8005fba:	1c10      	adds	r0, r2, #0
 8005fbc:	8008      	strh	r0, [r1, #0]
 8005fbe:	3102      	adds	r1, #2
 8005fc0:	2041      	movs	r0, #65	@ 0x41
 8005fc2:	8008      	strh	r0, [r1, #0]
 8005fc4:	480a      	ldr	r0, [pc, #40]	@ (0x8005ff0)
 8005fc6:	4a0b      	ldr	r2, [pc, #44]	@ (0x8005ff4)
 8005fc8:	8814      	ldrh	r4, [r2, #0]
 8005fca:	8004      	strh	r4, [r0, #0]
 8005fcc:	2000      	movs	r0, #0
 8005fce:	8010      	strh	r0, [r2, #0]
 8005fd0:	4b09      	ldr	r3, [pc, #36]	@ (0x8005ff8)
 8005fd2:	8818      	ldrh	r0, [r3, #0]
 8005fd4:	2140      	movs	r1, #64	@ 0x40
 8005fd6:	4308      	orrs	r0, r1
 8005fd8:	8018      	strh	r0, [r3, #0]
 8005fda:	8014      	strh	r4, [r2, #0]
 8005fdc:	bc10      	pop	{r4}
 8005fde:	bc01      	pop	{r0}
 8005fe0:	4700      	bx	r0
 8005fe2:	0000      	movs	r0, r0
 8005fe4:	2fe0      	cmp	r7, #224	@ 0xe0
 8005fe6:	0300      	lsls	r0, r0, #12
 8005fe8:	010c      	lsls	r4, r1, #4
 8005fea:	0400      	lsls	r0, r0, #16
 8005fec:	ff3b 0000 	vhadd.u<illegal width 64>	d0, d11, d0
 8005ff0:	3fa4      	subs	r7, #164	@ 0xa4
 8005ff2:	0300      	lsls	r0, r0, #12
 8005ff4:	0208      	lsls	r0, r1, #8
 8005ff6:	0400      	lsls	r0, r0, #16
 8005ff8:	0200      	lsls	r0, r0, #8
 8005ffa:	0400      	lsls	r0, r0, #16
 8005ffc:	b5f0      	push	{r4, r5, r6, r7, lr}
 8005ffe:	4657      	mov	r7, sl
