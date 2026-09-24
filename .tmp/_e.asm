
configs/POKEMON_RUBY_AXVJ00/hook/out/game.elf:     file format elf32-littlearm


Disassembly of section .text:

08800324 <chs_emit.isra.0>:
 8800324:	b5f0      	push	{r4, r5, r6, r7, lr}
 8800326:	4657      	mov	r7, sl
 8800328:	464e      	mov	r6, r9
 880032a:	46de      	mov	lr, fp
 880032c:	4645      	mov	r5, r8
 880032e:	b5e0      	push	{r5, r6, r7, lr}
 8800330:	b0b7      	sub	sp, #220	@ 0xdc
 8800332:	930b      	str	r3, [sp, #44]	@ 0x2c
 8800334:	9b40      	ldr	r3, [sp, #256]	@ 0x100
 8800336:	0004      	movs	r4, r0
 8800338:	000e      	movs	r6, r1
 880033a:	4692      	mov	sl, r2
 880033c:	2b00      	cmp	r3, #0
 880033e:	d100      	bne.n	8800342 <chs_emit.isra.0+0x1e>
 8800340:	9240      	str	r2, [sp, #256]	@ 0x100
 8800342:	2e02      	cmp	r6, #2
 8800344:	d100      	bne.n	8800348 <chs_emit.isra.0+0x24>
 8800346:	e1c1      	b.n	88006cc <chs_emit.isra.0+0x3a8>
 8800348:	7862      	ldrb	r2, [r4, #1]
 880034a:	7823      	ldrb	r3, [r4, #0]
 880034c:	0212      	lsls	r2, r2, #8
 880034e:	431a      	orrs	r2, r3
 8800350:	78a3      	ldrb	r3, [r4, #2]
 8800352:	78e5      	ldrb	r5, [r4, #3]
 8800354:	041b      	lsls	r3, r3, #16
 8800356:	4313      	orrs	r3, r2
 8800358:	0020      	movs	r0, r4
 880035a:	062d      	lsls	r5, r5, #24
 880035c:	431d      	orrs	r5, r3
 880035e:	2707      	movs	r7, #7
 8800360:	f000 fe12 	bl	8800f88 <v8_phase_get>
 8800364:	4653      	mov	r3, sl
 8800366:	4007      	ands	r7, r0
 8800368:	19db      	adds	r3, r3, r7
 880036a:	08db      	lsrs	r3, r3, #3
 880036c:	469b      	mov	fp, r3
 880036e:	d018      	beq.n	88003a2 <chs_emit.isra.0+0x7e>
 8800370:	2d00      	cmp	r5, #0
 8800372:	d00b      	beq.n	880038c <chs_emit.isra.0+0x68>
 8800374:	7b6a      	ldrb	r2, [r5, #13]
 8800376:	7b2b      	ldrb	r3, [r5, #12]
 8800378:	0212      	lsls	r2, r2, #8
 880037a:	431a      	orrs	r2, r3
 880037c:	7bab      	ldrb	r3, [r5, #14]
 880037e:	041b      	lsls	r3, r3, #16
 8800380:	4313      	orrs	r3, r2
 8800382:	7bea      	ldrb	r2, [r5, #15]
 8800384:	0612      	lsls	r2, r2, #24
 8800386:	431a      	orrs	r2, r3
 8800388:	4690      	mov	r8, r2
 880038a:	d119      	bne.n	88003c0 <chs_emit.isra.0+0x9c>
 880038c:	2e01      	cmp	r6, #1
 880038e:	d90b      	bls.n	88003a8 <chs_emit.isra.0+0x84>
 8800390:	b037      	add	sp, #220	@ 0xdc
 8800392:	bcf0      	pop	{r4, r5, r6, r7}
 8800394:	46bb      	mov	fp, r7
 8800396:	46b2      	mov	sl, r6
 8800398:	46a9      	mov	r9, r5
 880039a:	46a0      	mov	r8, r4
 880039c:	bcf0      	pop	{r4, r5, r6, r7}
 880039e:	bc01      	pop	{r0}
 88003a0:	4700      	bx	r0
 88003a2:	3301      	adds	r3, #1
 88003a4:	469b      	mov	fp, r3
 88003a6:	e7e3      	b.n	8800370 <chs_emit.isra.0+0x4c>
 88003a8:	465b      	mov	r3, fp
 88003aa:	005a      	lsls	r2, r3, #1
 88003ac:	7e63      	ldrb	r3, [r4, #25]
 88003ae:	7e21      	ldrb	r1, [r4, #24]
 88003b0:	021b      	lsls	r3, r3, #8
 88003b2:	430b      	orrs	r3, r1
 88003b4:	18d3      	adds	r3, r2, r3
 88003b6:	041a      	lsls	r2, r3, #16
 88003b8:	0e12      	lsrs	r2, r2, #24
 88003ba:	7623      	strb	r3, [r4, #24]
 88003bc:	7662      	strb	r2, [r4, #25]
 88003be:	e7e7      	b.n	8800390 <chs_emit.isra.0+0x6c>
 88003c0:	4bbf      	ldr	r3, [pc, #764]	@ (88006c0 <chs_emit.isra.0+0x39c>)
 88003c2:	781a      	ldrb	r2, [r3, #0]
 88003c4:	2a00      	cmp	r2, #0
 88003c6:	d100      	bne.n	88003ca <chs_emit.isra.0+0xa6>
 88003c8:	7b22      	ldrb	r2, [r4, #12]
 88003ca:	7aa3      	ldrb	r3, [r4, #10]
 88003cc:	9311      	str	r3, [sp, #68]	@ 0x44
 88003ce:	7ee3      	ldrb	r3, [r4, #27]
 88003d0:	7b60      	ldrb	r0, [r4, #13]
 88003d2:	930c      	str	r3, [sp, #48]	@ 0x30
 88003d4:	7ba3      	ldrb	r3, [r4, #14]
 88003d6:	4699      	mov	r9, r3
 88003d8:	0203      	lsls	r3, r0, #8
 88003da:	0401      	lsls	r1, r0, #16
 88003dc:	4303      	orrs	r3, r0
 88003de:	430b      	orrs	r3, r1
 88003e0:	2136      	movs	r1, #54	@ 0x36
 88003e2:	0600      	lsls	r0, r0, #24
 88003e4:	4303      	orrs	r3, r0
 88003e6:	9319      	str	r3, [sp, #100]	@ 0x64
 88003e8:	9316      	str	r3, [sp, #88]	@ 0x58
 88003ea:	9317      	str	r3, [sp, #92]	@ 0x5c
 88003ec:	9318      	str	r3, [sp, #96]	@ 0x60
 88003ee:	ab0c      	add	r3, sp, #48	@ 0x30
 88003f0:	185b      	adds	r3, r3, r1
 88003f2:	4649      	mov	r1, r9
 88003f4:	7019      	strb	r1, [r3, #0]
 88003f6:	2137      	movs	r1, #55	@ 0x37
 88003f8:	ab0c      	add	r3, sp, #48	@ 0x30
 88003fa:	185b      	adds	r3, r3, r1
 88003fc:	701a      	strb	r2, [r3, #0]
 88003fe:	4643      	mov	r3, r8
 8800400:	22c0      	movs	r2, #192	@ 0xc0
 8800402:	0bdb      	lsrs	r3, r3, #15
 8800404:	03db      	lsls	r3, r3, #15
 8800406:	04d2      	lsls	r2, r2, #19
 8800408:	4293      	cmp	r3, r2
 880040a:	d100      	bne.n	880040e <chs_emit.isra.0+0xea>
 880040c:	e1dc      	b.n	88007c8 <chs_emit.isra.0+0x4a4>
 880040e:	7de3      	ldrb	r3, [r4, #23]
 8800410:	7da2      	ldrb	r2, [r4, #22]
 8800412:	021b      	lsls	r3, r3, #8
 8800414:	4313      	orrs	r3, r2
 8800416:	2284      	movs	r2, #132	@ 0x84
 8800418:	0092      	lsls	r2, r2, #2
 880041a:	4694      	mov	ip, r2
 880041c:	4463      	add	r3, ip
 880041e:	041b      	lsls	r3, r3, #16
 8800420:	0c1b      	lsrs	r3, r3, #16
 8800422:	4699      	mov	r9, r3
 8800424:	2301      	movs	r3, #1
 8800426:	930f      	str	r3, [sp, #60]	@ 0x3c
 8800428:	335b      	adds	r3, #91	@ 0x5b
 880042a:	9310      	str	r3, [sp, #64]	@ 0x40
 880042c:	9b41      	ldr	r3, [sp, #260]	@ 0x104
 880042e:	00db      	lsls	r3, r3, #3
 8800430:	930d      	str	r3, [sp, #52]	@ 0x34
 8800432:	2f00      	cmp	r7, #0
 8800434:	d00f      	beq.n	8800456 <chs_emit.isra.0+0x132>
 8800436:	4ba3      	ldr	r3, [pc, #652]	@ (88006c4 <chs_emit.isra.0+0x3a0>)
 8800438:	0020      	movs	r0, r4
 880043a:	f000 fc5d 	bl	8800cf8 <PrintNextChar_Hook+0xb4>
 880043e:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 8800440:	433b      	orrs	r3, r7
 8800442:	930d      	str	r3, [sp, #52]	@ 0x34
 8800444:	2800      	cmp	r0, #0
 8800446:	d006      	beq.n	8800456 <chs_emit.isra.0+0x132>
 8800448:	8803      	ldrh	r3, [r0, #0]
 880044a:	059b      	lsls	r3, r3, #22
 880044c:	0d9a      	lsrs	r2, r3, #22
 880044e:	920e      	str	r2, [sp, #56]	@ 0x38
 8800450:	454a      	cmp	r2, r9
 8800452:	d300      	bcc.n	8800456 <chs_emit.isra.0+0x132>
 8800454:	e1cc      	b.n	88007f0 <chs_emit.isra.0+0x4cc>
 8800456:	2300      	movs	r3, #0
 8800458:	2200      	movs	r2, #0
 880045a:	930e      	str	r3, [sp, #56]	@ 0x38
 880045c:	7863      	ldrb	r3, [r4, #1]
 880045e:	7821      	ldrb	r1, [r4, #0]
 8800460:	021b      	lsls	r3, r3, #8
 8800462:	430b      	orrs	r3, r1
 8800464:	78a1      	ldrb	r1, [r4, #2]
 8800466:	0409      	lsls	r1, r1, #16
 8800468:	4319      	orrs	r1, r3
 880046a:	78e3      	ldrb	r3, [r4, #3]
 880046c:	061b      	lsls	r3, r3, #24
 880046e:	430b      	orrs	r3, r1
 8800470:	d100      	bne.n	8800474 <chs_emit.isra.0+0x150>
 8800472:	e78b      	b.n	880038c <chs_emit.isra.0+0x68>
 8800474:	7b58      	ldrb	r0, [r3, #13]
 8800476:	7b19      	ldrb	r1, [r3, #12]
 8800478:	0200      	lsls	r0, r0, #8
 880047a:	4308      	orrs	r0, r1
 880047c:	7b99      	ldrb	r1, [r3, #14]
 880047e:	7bdb      	ldrb	r3, [r3, #15]
 8800480:	0409      	lsls	r1, r1, #16
 8800482:	4301      	orrs	r1, r0
 8800484:	061b      	lsls	r3, r3, #24
 8800486:	430b      	orrs	r3, r1
 8800488:	d100      	bne.n	880048c <chs_emit.isra.0+0x168>
 880048a:	e77f      	b.n	880038c <chs_emit.isra.0+0x68>
 880048c:	21c0      	movs	r1, #192	@ 0xc0
 880048e:	0bdb      	lsrs	r3, r3, #15
 8800490:	03db      	lsls	r3, r3, #15
 8800492:	04c9      	lsls	r1, r1, #19
 8800494:	428b      	cmp	r3, r1
 8800496:	d100      	bne.n	880049a <chs_emit.isra.0+0x176>
 8800498:	e19e      	b.n	88007d8 <chs_emit.isra.0+0x4b4>
 880049a:	7de3      	ldrb	r3, [r4, #23]
 880049c:	7da1      	ldrb	r1, [r4, #22]
 880049e:	021b      	lsls	r3, r3, #8
 88004a0:	430b      	orrs	r3, r1
 88004a2:	21e0      	movs	r1, #224	@ 0xe0
 88004a4:	4699      	mov	r9, r3
 88004a6:	2380      	movs	r3, #128	@ 0x80
 88004a8:	0089      	lsls	r1, r1, #2
 88004aa:	4449      	add	r1, r9
 88004ac:	00db      	lsls	r3, r3, #3
 88004ae:	4299      	cmp	r1, r3
 88004b0:	d900      	bls.n	88004b4 <chs_emit.isra.0+0x190>
 88004b2:	e76b      	b.n	880038c <chs_emit.isra.0+0x68>
 88004b4:	2001      	movs	r0, #1
 88004b6:	990d      	ldr	r1, [sp, #52]	@ 0x34
 88004b8:	f7ff fdec 	bl	8800094 <chs_slot_for>
 88004bc:	2384      	movs	r3, #132	@ 0x84
 88004be:	009b      	lsls	r3, r3, #2
 88004c0:	444b      	add	r3, r9
 88004c2:	0080      	lsls	r0, r0, #2
 88004c4:	181b      	adds	r3, r3, r0
 88004c6:	041b      	lsls	r3, r3, #16
 88004c8:	0c1a      	lsrs	r2, r3, #16
 88004ca:	9214      	str	r2, [sp, #80]	@ 0x50
 88004cc:	2b00      	cmp	r3, #0
 88004ce:	d100      	bne.n	88004d2 <chs_emit.isra.0+0x1ae>
 88004d0:	e75c      	b.n	880038c <chs_emit.isra.0+0x68>
 88004d2:	2308      	movs	r3, #8
 88004d4:	1bdb      	subs	r3, r3, r7
 88004d6:	4699      	mov	r9, r3
 88004d8:	9b40      	ldr	r3, [sp, #256]	@ 0x100
 88004da:	4599      	cmp	r9, r3
 88004dc:	d900      	bls.n	88004e0 <chs_emit.isra.0+0x1bc>
 88004de:	4699      	mov	r9, r3
 88004e0:	464a      	mov	r2, r9
 88004e2:	9b40      	ldr	r3, [sp, #256]	@ 0x100
 88004e4:	1a9b      	subs	r3, r3, r2
 88004e6:	930d      	str	r3, [sp, #52]	@ 0x34
 88004e8:	9b40      	ldr	r3, [sp, #256]	@ 0x100
 88004ea:	9a14      	ldr	r2, [sp, #80]	@ 0x50
 88004ec:	454b      	cmp	r3, r9
 88004ee:	d100      	bne.n	88004f2 <chs_emit.isra.0+0x1ce>
 88004f0:	e1b1      	b.n	8800856 <chs_emit.isra.0+0x532>
 88004f2:	1c93      	adds	r3, r2, #2
 88004f4:	041b      	lsls	r3, r3, #16
 88004f6:	0c1b      	lsrs	r3, r3, #16
 88004f8:	930f      	str	r3, [sp, #60]	@ 0x3c
 88004fa:	0153      	lsls	r3, r2, #5
 88004fc:	4443      	add	r3, r8
 88004fe:	9313      	str	r3, [sp, #76]	@ 0x4c
 8800500:	1c53      	adds	r3, r2, #1
 8800502:	9315      	str	r3, [sp, #84]	@ 0x54
 8800504:	015b      	lsls	r3, r3, #5
 8800506:	4443      	add	r3, r8
 8800508:	9312      	str	r3, [sp, #72]	@ 0x48
 880050a:	2f00      	cmp	r7, #0
 880050c:	d000      	beq.n	8800510 <chs_emit.isra.0+0x1ec>
 880050e:	e1ae      	b.n	880086e <chs_emit.isra.0+0x54a>
 8800510:	a91e      	add	r1, sp, #120	@ 0x78
 8800512:	ab26      	add	r3, sp, #152	@ 0x98
 8800514:	464a      	mov	r2, r9
 8800516:	9310      	str	r3, [sp, #64]	@ 0x40
 8800518:	9300      	str	r3, [sp, #0]
 880051a:	910e      	str	r1, [sp, #56]	@ 0x38
 880051c:	000b      	movs	r3, r1
 880051e:	980b      	ldr	r0, [sp, #44]	@ 0x2c
 8800520:	2100      	movs	r1, #0
 8800522:	f000 fca7 	bl	8800e74 <extract_cols>
 8800526:	a916      	add	r1, sp, #88	@ 0x58
 8800528:	464b      	mov	r3, r9
 880052a:	9101      	str	r1, [sp, #4]
 880052c:	9a0e      	ldr	r2, [sp, #56]	@ 0x38
 880052e:	2100      	movs	r1, #0
 8800530:	9700      	str	r7, [sp, #0]
 8800532:	9813      	ldr	r0, [sp, #76]	@ 0x4c
 8800534:	f000 fbe4 	bl	8800d00 <blend_glyph_4bpp>
 8800538:	a916      	add	r1, sp, #88	@ 0x58
 880053a:	9101      	str	r1, [sp, #4]
 880053c:	464b      	mov	r3, r9
 880053e:	2100      	movs	r1, #0
 8800540:	9700      	str	r7, [sp, #0]
 8800542:	9a10      	ldr	r2, [sp, #64]	@ 0x40
 8800544:	9812      	ldr	r0, [sp, #72]	@ 0x48
 8800546:	f000 fbdb 	bl	8800d00 <blend_glyph_4bpp>
 880054a:	9b10      	ldr	r3, [sp, #64]	@ 0x40
 880054c:	4649      	mov	r1, r9
 880054e:	9300      	str	r3, [sp, #0]
 8800550:	9a0d      	ldr	r2, [sp, #52]	@ 0x34
 8800552:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 8800554:	980b      	ldr	r0, [sp, #44]	@ 0x2c
 8800556:	f000 fc8d 	bl	8800e74 <extract_cols>
 880055a:	990f      	ldr	r1, [sp, #60]	@ 0x3c
 880055c:	ab16      	add	r3, sp, #88	@ 0x58
 880055e:	0149      	lsls	r1, r1, #5
 8800560:	0008      	movs	r0, r1
 8800562:	9301      	str	r3, [sp, #4]
 8800564:	2300      	movs	r3, #0
 8800566:	910b      	str	r1, [sp, #44]	@ 0x2c
 8800568:	9300      	str	r3, [sp, #0]
 880056a:	2100      	movs	r1, #0
 880056c:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 880056e:	9a0e      	ldr	r2, [sp, #56]	@ 0x38
 8800570:	4440      	add	r0, r8
 8800572:	f000 fbc5 	bl	8800d00 <blend_glyph_4bpp>
 8800576:	990f      	ldr	r1, [sp, #60]	@ 0x3c
 8800578:	1c4b      	adds	r3, r1, #1
 880057a:	0159      	lsls	r1, r3, #5
 880057c:	0008      	movs	r0, r1
 880057e:	9112      	str	r1, [sp, #72]	@ 0x48
 8800580:	2100      	movs	r1, #0
 8800582:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 8800584:	aa16      	add	r2, sp, #88	@ 0x58
 8800586:	9201      	str	r2, [sp, #4]
 8800588:	4440      	add	r0, r8
 880058a:	9a10      	ldr	r2, [sp, #64]	@ 0x40
 880058c:	9100      	str	r1, [sp, #0]
 880058e:	4698      	mov	r8, r3
 8800590:	f000 fbb6 	bl	8800d00 <blend_glyph_4bpp>
 8800594:	7863      	ldrb	r3, [r4, #1]
 8800596:	7822      	ldrb	r2, [r4, #0]
 8800598:	021b      	lsls	r3, r3, #8
 880059a:	4313      	orrs	r3, r2
 880059c:	78a2      	ldrb	r2, [r4, #2]
 880059e:	0412      	lsls	r2, r2, #16
 88005a0:	431a      	orrs	r2, r3
 88005a2:	78e3      	ldrb	r3, [r4, #3]
 88005a4:	061b      	lsls	r3, r3, #24
 88005a6:	4313      	orrs	r3, r2
 88005a8:	d048      	beq.n	880063c <chs_emit.isra.0+0x318>
 88005aa:	4642      	mov	r2, r8
 88005ac:	2a07      	cmp	r2, #7
 88005ae:	d845      	bhi.n	880063c <chs_emit.isra.0+0x318>
 88005b0:	7b59      	ldrb	r1, [r3, #13]
 88005b2:	7b1a      	ldrb	r2, [r3, #12]
 88005b4:	0209      	lsls	r1, r1, #8
 88005b6:	4311      	orrs	r1, r2
 88005b8:	7b9a      	ldrb	r2, [r3, #14]
 88005ba:	7bdb      	ldrb	r3, [r3, #15]
 88005bc:	0412      	lsls	r2, r2, #16
 88005be:	430a      	orrs	r2, r1
 88005c0:	061b      	lsls	r3, r3, #24
 88005c2:	4313      	orrs	r3, r2
 88005c4:	4698      	mov	r8, r3
 88005c6:	d039      	beq.n	880063c <chs_emit.isra.0+0x318>
 88005c8:	4b3d      	ldr	r3, [pc, #244]	@ (88006c0 <chs_emit.isra.0+0x39c>)
 88005ca:	781a      	ldrb	r2, [r3, #0]
 88005cc:	2a00      	cmp	r2, #0
 88005ce:	d100      	bne.n	88005d2 <chs_emit.isra.0+0x2ae>
 88005d0:	7b22      	ldrb	r2, [r4, #12]
 88005d2:	7b60      	ldrb	r0, [r4, #13]
 88005d4:	7ba1      	ldrb	r1, [r4, #14]
 88005d6:	0203      	lsls	r3, r0, #8
 88005d8:	9110      	str	r1, [sp, #64]	@ 0x40
 88005da:	4303      	orrs	r3, r0
 88005dc:	0401      	lsls	r1, r0, #16
 88005de:	430b      	orrs	r3, r1
 88005e0:	0600      	lsls	r0, r0, #24
 88005e2:	4303      	orrs	r3, r0
 88005e4:	931a      	str	r3, [sp, #104]	@ 0x68
 88005e6:	931b      	str	r3, [sp, #108]	@ 0x6c
 88005e8:	931c      	str	r3, [sp, #112]	@ 0x70
 88005ea:	931d      	str	r3, [sp, #116]	@ 0x74
 88005ec:	ab1a      	add	r3, sp, #104	@ 0x68
 88005ee:	73da      	strb	r2, [r3, #15]
 88005f0:	2200      	movs	r2, #0
 88005f2:	9910      	ldr	r1, [sp, #64]	@ 0x40
 88005f4:	930e      	str	r3, [sp, #56]	@ 0x38
 88005f6:	7399      	strb	r1, [r3, #14]
 88005f8:	ab2e      	add	r3, sp, #184	@ 0xb8
 88005fa:	9310      	str	r3, [sp, #64]	@ 0x40
 88005fc:	c304      	stmia	r3!, {r2}
 88005fe:	a936      	add	r1, sp, #216	@ 0xd8
 8800600:	4299      	cmp	r1, r3
 8800602:	d1fb      	bne.n	88005fc <chs_emit.isra.0+0x2d8>
 8800604:	464b      	mov	r3, r9
 8800606:	9a40      	ldr	r2, [sp, #256]	@ 0x100
 8800608:	1a9b      	subs	r3, r3, r2
 880060a:	2208      	movs	r2, #8
 880060c:	4691      	mov	r9, r2
 880060e:	980b      	ldr	r0, [sp, #44]	@ 0x2c
 8800610:	9a0d      	ldr	r2, [sp, #52]	@ 0x34
 8800612:	4499      	add	r9, r3
 8800614:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 8800616:	2100      	movs	r1, #0
 8800618:	9301      	str	r3, [sp, #4]
 880061a:	9200      	str	r2, [sp, #0]
 880061c:	464b      	mov	r3, r9
 880061e:	9a10      	ldr	r2, [sp, #64]	@ 0x40
 8800620:	4440      	add	r0, r8
 8800622:	f000 fb6d 	bl	8800d00 <blend_glyph_4bpp>
 8800626:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 8800628:	9812      	ldr	r0, [sp, #72]	@ 0x48
 880062a:	9301      	str	r3, [sp, #4]
 880062c:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 880062e:	2100      	movs	r1, #0
 8800630:	9300      	str	r3, [sp, #0]
 8800632:	9a10      	ldr	r2, [sp, #64]	@ 0x40
 8800634:	464b      	mov	r3, r9
 8800636:	4440      	add	r0, r8
 8800638:	f000 fb62 	bl	8800d00 <blend_glyph_4bpp>
 880063c:	465b      	mov	r3, fp
 880063e:	061b      	lsls	r3, r3, #24
 8800640:	0e1b      	lsrs	r3, r3, #24
 8800642:	4698      	mov	r8, r3
 8800644:	4b20      	ldr	r3, [pc, #128]	@ (88006c8 <chs_emit.isra.0+0x3a4>)
 8800646:	6819      	ldr	r1, [r3, #0]
 8800648:	7e63      	ldrb	r3, [r4, #25]
 880064a:	7e22      	ldrb	r2, [r4, #24]
 880064c:	0609      	lsls	r1, r1, #24
 880064e:	0e09      	lsrs	r1, r1, #24
 8800650:	021b      	lsls	r3, r3, #8
 8800652:	7da0      	ldrb	r0, [r4, #22]
 8800654:	4313      	orrs	r3, r2
 8800656:	7de2      	ldrb	r2, [r4, #23]
 8800658:	9109      	str	r1, [sp, #36]	@ 0x24
 880065a:	2107      	movs	r1, #7
 880065c:	0212      	lsls	r2, r2, #8
 880065e:	4302      	orrs	r2, r0
 8800660:	9811      	ldr	r0, [sp, #68]	@ 0x44
 8800662:	4001      	ands	r1, r0
 8800664:	9108      	str	r1, [sp, #32]
 8800666:	4641      	mov	r1, r8
 8800668:	9706      	str	r7, [sp, #24]
 880066a:	9107      	str	r1, [sp, #28]
 880066c:	9f14      	ldr	r7, [sp, #80]	@ 0x50
 880066e:	990f      	ldr	r1, [sp, #60]	@ 0x3c
 8800670:	9704      	str	r7, [sp, #16]
 8800672:	9105      	str	r1, [sp, #20]
 8800674:	7f61      	ldrb	r1, [r4, #29]
 8800676:	9103      	str	r1, [sp, #12]
 8800678:	990c      	ldr	r1, [sp, #48]	@ 0x30
 880067a:	9102      	str	r1, [sp, #8]
 880067c:	7f21      	ldrb	r1, [r4, #28]
 880067e:	9101      	str	r1, [sp, #4]
 8800680:	7ea1      	ldrb	r1, [r4, #26]
 8800682:	0020      	movs	r0, r4
 8800684:	9100      	str	r1, [sp, #0]
 8800686:	0029      	movs	r1, r5
 8800688:	f000 fd90 	bl	88011ac <trace_glyph>
 880068c:	9b15      	ldr	r3, [sp, #84]	@ 0x54
 880068e:	041a      	lsls	r2, r3, #16
 8800690:	0039      	movs	r1, r7
 8800692:	0020      	movs	r0, r4
 8800694:	0c12      	lsrs	r2, r2, #16
 8800696:	7ea5      	ldrb	r5, [r4, #26]
 8800698:	f7ff fcbe 	bl	8800018 <UpdateTilemap_Origin>
 880069c:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 880069e:	76a5      	strb	r5, [r4, #26]
 88006a0:	2b00      	cmp	r3, #0
 88006a2:	d000      	beq.n	88006a6 <chs_emit.isra.0+0x382>
 88006a4:	e116      	b.n	88008d4 <chs_emit.isra.0+0x5b0>
 88006a6:	9b0c      	ldr	r3, [sp, #48]	@ 0x30
 88006a8:	4443      	add	r3, r8
 88006aa:	76e3      	strb	r3, [r4, #27]
 88006ac:	4653      	mov	r3, sl
 88006ae:	0418      	lsls	r0, r3, #16
 88006b0:	0c00      	lsrs	r0, r0, #16
 88006b2:	f000 fc8f 	bl	8800fd4 <v8_phase_advance>
 88006b6:	2e01      	cmp	r6, #1
 88006b8:	d900      	bls.n	88006bc <chs_emit.isra.0+0x398>
 88006ba:	e669      	b.n	8800390 <chs_emit.isra.0+0x6c>
 88006bc:	e674      	b.n	88003a8 <chs_emit.isra.0+0x84>
 88006be:	46c0      	nop			@ (mov r8, r8)
 88006c0:	0203ffd1 	.word	0x0203ffd1
 88006c4:	08003709 	.word	0x08003709
 88006c8:	0203e8a8 	.word	0x0203e8a8
 88006cc:	2221      	movs	r2, #33	@ 0x21
 88006ce:	2320      	movs	r3, #32
 88006d0:	5ca2      	ldrb	r2, [r4, r2]
 88006d2:	5ce3      	ldrb	r3, [r4, r3]
 88006d4:	0212      	lsls	r2, r2, #8
 88006d6:	431a      	orrs	r2, r3
 88006d8:	2322      	movs	r3, #34	@ 0x22
 88006da:	5ce3      	ldrb	r3, [r4, r3]
 88006dc:	041b      	lsls	r3, r3, #16
 88006de:	4313      	orrs	r3, r2
 88006e0:	2223      	movs	r2, #35	@ 0x23
 88006e2:	5ca5      	ldrb	r5, [r4, r2]
 88006e4:	062d      	lsls	r5, r5, #24
 88006e6:	431d      	orrs	r5, r3
 88006e8:	d100      	bne.n	88006ec <chs_emit.isra.0+0x3c8>
 88006ea:	e651      	b.n	8800390 <chs_emit.isra.0+0x6c>
 88006ec:	0020      	movs	r0, r4
 88006ee:	f000 fc4b 	bl	8800f88 <v8_phase_get>
 88006f2:	2307      	movs	r3, #7
 88006f4:	2708      	movs	r7, #8
 88006f6:	4003      	ands	r3, r0
 88006f8:	4699      	mov	r9, r3
 88006fa:	1aff      	subs	r7, r7, r3
 88006fc:	9b40      	ldr	r3, [sp, #256]	@ 0x100
 88006fe:	429f      	cmp	r7, r3
 8800700:	d900      	bls.n	8800704 <chs_emit.isra.0+0x3e0>
 8800702:	001f      	movs	r7, r3
 8800704:	4656      	mov	r6, sl
 8800706:	9b40      	ldr	r3, [sp, #256]	@ 0x100
 8800708:	444e      	add	r6, r9
 880070a:	1bdb      	subs	r3, r3, r7
 880070c:	930c      	str	r3, [sp, #48]	@ 0x30
 880070e:	08f3      	lsrs	r3, r6, #3
 8800710:	930d      	str	r3, [sp, #52]	@ 0x34
 8800712:	d101      	bne.n	8800718 <chs_emit.isra.0+0x3f4>
 8800714:	3301      	adds	r3, #1
 8800716:	930d      	str	r3, [sp, #52]	@ 0x34
 8800718:	4bac      	ldr	r3, [pc, #688]	@ (88009cc <chs_emit.isra.0+0x6a8>)
 880071a:	781a      	ldrb	r2, [r3, #0]
 880071c:	2a00      	cmp	r2, #0
 880071e:	d100      	bne.n	8800722 <chs_emit.isra.0+0x3fe>
 8800720:	7b22      	ldrb	r2, [r4, #12]
 8800722:	7b60      	ldrb	r0, [r4, #13]
 8800724:	0203      	lsls	r3, r0, #8
 8800726:	0406      	lsls	r6, r0, #16
 8800728:	4303      	orrs	r3, r0
 880072a:	4333      	orrs	r3, r6
 880072c:	2600      	movs	r6, #0
 880072e:	0600      	lsls	r0, r0, #24
 8800730:	4303      	orrs	r3, r0
 8800732:	7ba1      	ldrb	r1, [r4, #14]
 8800734:	931a      	str	r3, [sp, #104]	@ 0x68
 8800736:	931b      	str	r3, [sp, #108]	@ 0x6c
 8800738:	931c      	str	r3, [sp, #112]	@ 0x70
 880073a:	931d      	str	r3, [sp, #116]	@ 0x74
 880073c:	ab1a      	add	r3, sp, #104	@ 0x68
 880073e:	930e      	str	r3, [sp, #56]	@ 0x38
 8800740:	7399      	strb	r1, [r3, #14]
 8800742:	73da      	strb	r2, [r3, #15]
 8800744:	ab2e      	add	r3, sp, #184	@ 0xb8
 8800746:	9310      	str	r3, [sp, #64]	@ 0x40
 8800748:	c340      	stmia	r3!, {r6}
 880074a:	aa36      	add	r2, sp, #216	@ 0xd8
 880074c:	429a      	cmp	r2, r3
 880074e:	d1fb      	bne.n	8800748 <chs_emit.isra.0+0x424>
 8800750:	ab26      	add	r3, sp, #152	@ 0x98
 8800752:	469b      	mov	fp, r3
 8800754:	003a      	movs	r2, r7
 8800756:	2100      	movs	r1, #0
 8800758:	9300      	str	r3, [sp, #0]
 880075a:	980b      	ldr	r0, [sp, #44]	@ 0x2c
 880075c:	ab1e      	add	r3, sp, #120	@ 0x78
 880075e:	f000 fb89 	bl	8800e74 <extract_cols>
 8800762:	464a      	mov	r2, r9
 8800764:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 8800766:	2100      	movs	r1, #0
 8800768:	9301      	str	r3, [sp, #4]
 880076a:	9200      	str	r2, [sp, #0]
 880076c:	003b      	movs	r3, r7
 880076e:	aa1e      	add	r2, sp, #120	@ 0x78
 8800770:	0028      	movs	r0, r5
 8800772:	f000 fac5 	bl	8800d00 <blend_glyph_4bpp>
 8800776:	2220      	movs	r2, #32
 8800778:	4694      	mov	ip, r2
 880077a:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 880077c:	44ac      	add	ip, r5
 880077e:	9301      	str	r3, [sp, #4]
 8800780:	464b      	mov	r3, r9
 8800782:	4660      	mov	r0, ip
 8800784:	9300      	str	r3, [sp, #0]
 8800786:	465a      	mov	r2, fp
 8800788:	003b      	movs	r3, r7
 880078a:	2100      	movs	r1, #0
 880078c:	900f      	str	r0, [sp, #60]	@ 0x3c
 880078e:	f000 fab7 	bl	8800d00 <blend_glyph_4bpp>
 8800792:	9b0c      	ldr	r3, [sp, #48]	@ 0x30
 8800794:	2b00      	cmp	r3, #0
 8800796:	d000      	beq.n	880079a <chs_emit.isra.0+0x476>
 8800798:	e0d7      	b.n	880094a <chs_emit.isra.0+0x626>
 880079a:	444f      	add	r7, r9
 880079c:	2f07      	cmp	r7, #7
 880079e:	d945      	bls.n	880082c <chs_emit.isra.0+0x508>
 88007a0:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 88007a2:	019e      	lsls	r6, r3, #6
 88007a4:	2320      	movs	r3, #32
 88007a6:	1976      	adds	r6, r6, r5
 88007a8:	54e6      	strb	r6, [r4, r3]
 88007aa:	0a32      	lsrs	r2, r6, #8
 88007ac:	3301      	adds	r3, #1
 88007ae:	54e2      	strb	r2, [r4, r3]
 88007b0:	0c32      	lsrs	r2, r6, #16
 88007b2:	3301      	adds	r3, #1
 88007b4:	54e2      	strb	r2, [r4, r3]
 88007b6:	0e36      	lsrs	r6, r6, #24
 88007b8:	3301      	adds	r3, #1
 88007ba:	54e6      	strb	r6, [r4, r3]
 88007bc:	4653      	mov	r3, sl
 88007be:	0418      	lsls	r0, r3, #16
 88007c0:	0c00      	lsrs	r0, r0, #16
 88007c2:	f000 fc07 	bl	8800fd4 <v8_phase_advance>
 88007c6:	e5e3      	b.n	8800390 <chs_emit.isra.0+0x6c>
 88007c8:	2300      	movs	r3, #0
 88007ca:	930f      	str	r3, [sp, #60]	@ 0x3c
 88007cc:	3328      	adds	r3, #40	@ 0x28
 88007ce:	9310      	str	r3, [sp, #64]	@ 0x40
 88007d0:	3339      	adds	r3, #57	@ 0x39
 88007d2:	33ff      	adds	r3, #255	@ 0xff
 88007d4:	4699      	mov	r9, r3
 88007d6:	e629      	b.n	880042c <chs_emit.isra.0+0x108>
 88007d8:	2000      	movs	r0, #0
 88007da:	990d      	ldr	r1, [sp, #52]	@ 0x34
 88007dc:	f7ff fc5a 	bl	8800094 <chs_slot_for>
 88007e0:	2827      	cmp	r0, #39	@ 0x27
 88007e2:	d900      	bls.n	88007e6 <chs_emit.isra.0+0x4c2>
 88007e4:	e5d2      	b.n	880038c <chs_emit.isra.0+0x68>
 88007e6:	3058      	adds	r0, #88	@ 0x58
 88007e8:	0480      	lsls	r0, r0, #18
 88007ea:	0c03      	lsrs	r3, r0, #16
 88007ec:	9314      	str	r3, [sp, #80]	@ 0x50
 88007ee:	e670      	b.n	88004d2 <chs_emit.isra.0+0x1ae>
 88007f0:	9b10      	ldr	r3, [sp, #64]	@ 0x40
 88007f2:	009b      	lsls	r3, r3, #2
 88007f4:	444b      	add	r3, r9
 88007f6:	429a      	cmp	r2, r3
 88007f8:	d300      	bcc.n	88007fc <chs_emit.isra.0+0x4d8>
 88007fa:	e62c      	b.n	8800456 <chs_emit.isra.0+0x132>
 88007fc:	464b      	mov	r3, r9
 88007fe:	0011      	movs	r1, r2
 8800800:	1ad2      	subs	r2, r2, r3
 8800802:	2303      	movs	r3, #3
 8800804:	4013      	ands	r3, r2
 8800806:	2b02      	cmp	r3, #2
 8800808:	d000      	beq.n	880080c <chs_emit.isra.0+0x4e8>
 880080a:	e624      	b.n	8800456 <chs_emit.isra.0+0x132>
 880080c:	2900      	cmp	r1, #0
 880080e:	d100      	bne.n	8800812 <chs_emit.isra.0+0x4ee>
 8800810:	e0d9      	b.n	88009c6 <chs_emit.isra.0+0x6a2>
 8800812:	9b0f      	ldr	r3, [sp, #60]	@ 0x3c
 8800814:	496e      	ldr	r1, [pc, #440]	@ (88009d0 <chs_emit.isra.0+0x6ac>)
 8800816:	0392      	lsls	r2, r2, #14
 8800818:	3b01      	subs	r3, #1
 880081a:	0c12      	lsrs	r2, r2, #16
 880081c:	00d2      	lsls	r2, r2, #3
 880081e:	400b      	ands	r3, r1
 8800820:	189b      	adds	r3, r3, r2
 8800822:	4a6c      	ldr	r2, [pc, #432]	@ (88009d4 <chs_emit.isra.0+0x6b0>)
 8800824:	4694      	mov	ip, r2
 8800826:	4463      	add	r3, ip
 8800828:	681a      	ldr	r2, [r3, #0]
 880082a:	e617      	b.n	880045c <chs_emit.isra.0+0x138>
 880082c:	2308      	movs	r3, #8
 880082e:	9a10      	ldr	r2, [sp, #64]	@ 0x40
 8800830:	1bdb      	subs	r3, r3, r7
 8800832:	4698      	mov	r8, r3
 8800834:	4691      	mov	r9, r2
 8800836:	9e0e      	ldr	r6, [sp, #56]	@ 0x38
 8800838:	2100      	movs	r1, #0
 880083a:	0028      	movs	r0, r5
 880083c:	9601      	str	r6, [sp, #4]
 880083e:	9700      	str	r7, [sp, #0]
 8800840:	f000 fa5e 	bl	8800d00 <blend_glyph_4bpp>
 8800844:	4643      	mov	r3, r8
 8800846:	464a      	mov	r2, r9
 8800848:	2100      	movs	r1, #0
 880084a:	9601      	str	r6, [sp, #4]
 880084c:	9700      	str	r7, [sp, #0]
 880084e:	980f      	ldr	r0, [sp, #60]	@ 0x3c
 8800850:	f000 fa56 	bl	8800d00 <blend_glyph_4bpp>
 8800854:	e7a4      	b.n	88007a0 <chs_emit.isra.0+0x47c>
 8800856:	0153      	lsls	r3, r2, #5
 8800858:	4443      	add	r3, r8
 880085a:	9313      	str	r3, [sp, #76]	@ 0x4c
 880085c:	1c53      	adds	r3, r2, #1
 880085e:	9315      	str	r3, [sp, #84]	@ 0x54
 8800860:	015b      	lsls	r3, r3, #5
 8800862:	4443      	add	r3, r8
 8800864:	9312      	str	r3, [sp, #72]	@ 0x48
 8800866:	2f00      	cmp	r7, #0
 8800868:	d051      	beq.n	880090e <chs_emit.isra.0+0x5ea>
 880086a:	2300      	movs	r3, #0
 880086c:	930f      	str	r3, [sp, #60]	@ 0x3c
 880086e:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 8800870:	2b00      	cmp	r3, #0
 8800872:	d03b      	beq.n	88008ec <chs_emit.isra.0+0x5c8>
 8800874:	0159      	lsls	r1, r3, #5
 8800876:	003a      	movs	r2, r7
 8800878:	9813      	ldr	r0, [sp, #76]	@ 0x4c
 880087a:	4441      	add	r1, r8
 880087c:	f7ff fcb0 	bl	88001e0 <copy_px_cols>
 8800880:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 8800882:	1c59      	adds	r1, r3, #1
 8800884:	0149      	lsls	r1, r1, #5
 8800886:	003a      	movs	r2, r7
 8800888:	9812      	ldr	r0, [sp, #72]	@ 0x48
 880088a:	4441      	add	r1, r8
 880088c:	f7ff fca8 	bl	88001e0 <copy_px_cols>
 8800890:	a91e      	add	r1, sp, #120	@ 0x78
 8800892:	ab26      	add	r3, sp, #152	@ 0x98
 8800894:	464a      	mov	r2, r9
 8800896:	9310      	str	r3, [sp, #64]	@ 0x40
 8800898:	9300      	str	r3, [sp, #0]
 880089a:	910e      	str	r1, [sp, #56]	@ 0x38
 880089c:	000b      	movs	r3, r1
 880089e:	980b      	ldr	r0, [sp, #44]	@ 0x2c
 88008a0:	2100      	movs	r1, #0
 88008a2:	f000 fae7 	bl	8800e74 <extract_cols>
 88008a6:	a916      	add	r1, sp, #88	@ 0x58
 88008a8:	464b      	mov	r3, r9
 88008aa:	9101      	str	r1, [sp, #4]
 88008ac:	9a0e      	ldr	r2, [sp, #56]	@ 0x38
 88008ae:	2100      	movs	r1, #0
 88008b0:	9700      	str	r7, [sp, #0]
 88008b2:	9813      	ldr	r0, [sp, #76]	@ 0x4c
 88008b4:	f000 fa24 	bl	8800d00 <blend_glyph_4bpp>
 88008b8:	a916      	add	r1, sp, #88	@ 0x58
 88008ba:	464b      	mov	r3, r9
 88008bc:	9101      	str	r1, [sp, #4]
 88008be:	9700      	str	r7, [sp, #0]
 88008c0:	2100      	movs	r1, #0
 88008c2:	9a10      	ldr	r2, [sp, #64]	@ 0x40
 88008c4:	9812      	ldr	r0, [sp, #72]	@ 0x48
 88008c6:	f000 fa1b 	bl	8800d00 <blend_glyph_4bpp>
 88008ca:	9b0d      	ldr	r3, [sp, #52]	@ 0x34
 88008cc:	2b00      	cmp	r3, #0
 88008ce:	d100      	bne.n	88008d2 <chs_emit.isra.0+0x5ae>
 88008d0:	e6b4      	b.n	880063c <chs_emit.isra.0+0x318>
 88008d2:	e63a      	b.n	880054a <chs_emit.isra.0+0x226>
 88008d4:	990f      	ldr	r1, [sp, #60]	@ 0x3c
 88008d6:	9b0c      	ldr	r3, [sp, #48]	@ 0x30
 88008d8:	1c4a      	adds	r2, r1, #1
 88008da:	3301      	adds	r3, #1
 88008dc:	0412      	lsls	r2, r2, #16
 88008de:	0020      	movs	r0, r4
 88008e0:	76e3      	strb	r3, [r4, #27]
 88008e2:	0c12      	lsrs	r2, r2, #16
 88008e4:	f7ff fb98 	bl	8800018 <UpdateTilemap_Origin>
 88008e8:	76a5      	strb	r5, [r4, #26]
 88008ea:	e6dc      	b.n	88006a6 <chs_emit.isra.0+0x382>
 88008ec:	2328      	movs	r3, #40	@ 0x28
 88008ee:	aa0c      	add	r2, sp, #48	@ 0x30
 88008f0:	18d2      	adds	r2, r2, r3
 88008f2:	0039      	movs	r1, r7
 88008f4:	9813      	ldr	r0, [sp, #76]	@ 0x4c
 88008f6:	7812      	ldrb	r2, [r2, #0]
 88008f8:	f7ff fca6 	bl	8800248 <clear_px_cols>
 88008fc:	2328      	movs	r3, #40	@ 0x28
 88008fe:	aa0c      	add	r2, sp, #48	@ 0x30
 8800900:	18d3      	adds	r3, r2, r3
 8800902:	0039      	movs	r1, r7
 8800904:	781a      	ldrb	r2, [r3, #0]
 8800906:	9812      	ldr	r0, [sp, #72]	@ 0x48
 8800908:	f7ff fc9e 	bl	8800248 <clear_px_cols>
 880090c:	e7c0      	b.n	8800890 <chs_emit.isra.0+0x56c>
 880090e:	ab26      	add	r3, sp, #152	@ 0x98
 8800910:	4698      	mov	r8, r3
 8800912:	464a      	mov	r2, r9
 8800914:	2100      	movs	r1, #0
 8800916:	9300      	str	r3, [sp, #0]
 8800918:	980b      	ldr	r0, [sp, #44]	@ 0x2c
 880091a:	ab1e      	add	r3, sp, #120	@ 0x78
 880091c:	f000 faaa 	bl	8800e74 <extract_cols>
 8800920:	ab16      	add	r3, sp, #88	@ 0x58
 8800922:	2100      	movs	r1, #0
 8800924:	9301      	str	r3, [sp, #4]
 8800926:	aa1e      	add	r2, sp, #120	@ 0x78
 8800928:	464b      	mov	r3, r9
 880092a:	9700      	str	r7, [sp, #0]
 880092c:	9813      	ldr	r0, [sp, #76]	@ 0x4c
 880092e:	f000 f9e7 	bl	8800d00 <blend_glyph_4bpp>
 8800932:	ab16      	add	r3, sp, #88	@ 0x58
 8800934:	9301      	str	r3, [sp, #4]
 8800936:	4642      	mov	r2, r8
 8800938:	464b      	mov	r3, r9
 880093a:	2100      	movs	r1, #0
 880093c:	9700      	str	r7, [sp, #0]
 880093e:	9812      	ldr	r0, [sp, #72]	@ 0x48
 8800940:	f000 f9de 	bl	8800d00 <blend_glyph_4bpp>
 8800944:	2300      	movs	r3, #0
 8800946:	930f      	str	r3, [sp, #60]	@ 0x3c
 8800948:	e678      	b.n	880063c <chs_emit.isra.0+0x318>
 880094a:	465b      	mov	r3, fp
 880094c:	9a0c      	ldr	r2, [sp, #48]	@ 0x30
 880094e:	0039      	movs	r1, r7
 8800950:	9300      	str	r3, [sp, #0]
 8800952:	980b      	ldr	r0, [sp, #44]	@ 0x2c
 8800954:	ab1e      	add	r3, sp, #120	@ 0x78
 8800956:	4691      	mov	r9, r2
 8800958:	f000 fa8c 	bl	8800e74 <extract_cols>
 880095c:	2340      	movs	r3, #64	@ 0x40
 880095e:	4698      	mov	r8, r3
 8800960:	9b0e      	ldr	r3, [sp, #56]	@ 0x38
 8800962:	9301      	str	r3, [sp, #4]
 8800964:	464b      	mov	r3, r9
 8800966:	44a8      	add	r8, r5
 8800968:	2100      	movs	r1, #0
 880096a:	9600      	str	r6, [sp, #0]
 880096c:	aa1e      	add	r2, sp, #120	@ 0x78
 880096e:	4640      	mov	r0, r8
 8800970:	930c      	str	r3, [sp, #48]	@ 0x30
 8800972:	f000 f9c5 	bl	8800d00 <blend_glyph_4bpp>
 8800976:	2160      	movs	r1, #96	@ 0x60
 8800978:	4689      	mov	r9, r1
 880097a:	9a0e      	ldr	r2, [sp, #56]	@ 0x38
 880097c:	9600      	str	r6, [sp, #0]
 880097e:	9e0c      	ldr	r6, [sp, #48]	@ 0x30
 8800980:	44a9      	add	r9, r5
 8800982:	9201      	str	r2, [sp, #4]
 8800984:	0033      	movs	r3, r6
 8800986:	465a      	mov	r2, fp
 8800988:	2100      	movs	r1, #0
 880098a:	4648      	mov	r0, r9
 880098c:	f000 f9b8 	bl	8800d00 <blend_glyph_4bpp>
 8800990:	2e07      	cmp	r6, #7
 8800992:	d900      	bls.n	8800996 <chs_emit.isra.0+0x672>
 8800994:	e704      	b.n	88007a0 <chs_emit.isra.0+0x47c>
 8800996:	9a10      	ldr	r2, [sp, #64]	@ 0x40
 8800998:	4693      	mov	fp, r2
 880099a:	9b40      	ldr	r3, [sp, #256]	@ 0x100
 880099c:	9e0e      	ldr	r6, [sp, #56]	@ 0x38
 880099e:	1aff      	subs	r7, r7, r3
 88009a0:	9b0c      	ldr	r3, [sp, #48]	@ 0x30
 88009a2:	3708      	adds	r7, #8
 88009a4:	9300      	str	r3, [sp, #0]
 88009a6:	2100      	movs	r1, #0
 88009a8:	003b      	movs	r3, r7
 88009aa:	4640      	mov	r0, r8
 88009ac:	9601      	str	r6, [sp, #4]
 88009ae:	f000 f9a7 	bl	8800d00 <blend_glyph_4bpp>
 88009b2:	9b0c      	ldr	r3, [sp, #48]	@ 0x30
 88009b4:	465a      	mov	r2, fp
 88009b6:	9300      	str	r3, [sp, #0]
 88009b8:	2100      	movs	r1, #0
 88009ba:	003b      	movs	r3, r7
 88009bc:	4648      	mov	r0, r9
 88009be:	9601      	str	r6, [sp, #4]
 88009c0:	f000 f99e 	bl	8800d00 <blend_glyph_4bpp>
 88009c4:	e6ec      	b.n	88007a0 <chs_emit.isra.0+0x47c>
 88009c6:	2200      	movs	r2, #0
 88009c8:	e548      	b.n	880045c <chs_emit.isra.0+0x138>
 88009ca:	46c0      	nop			@ (mov r8, r8)
 88009cc:	0203ffd1 	.word	0x0203ffd1
 88009d0:	fffffbb0 	.word	0xfffffbb0
 88009d4:	0203e458 	.word	0x0203e458
