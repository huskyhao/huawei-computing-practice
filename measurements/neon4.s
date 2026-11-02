	.arch armv8-a
	.file	"sum_neon.c"
	.text
	.align	2
	.p2align 4,,15
	.global	sum_neon4
	.type	sum_neon4, %function
sum_neon4:
.LFB3916:
	.cfi_startproc
	stp	x29, x30, [sp, -16]!
	.cfi_def_cfa_offset 16
	.cfi_offset 29, -16
	.cfi_offset 30, -8
	mov	x29, sp
	cmp	x1, 15
	bls	.L9
	movi	v26.4s, 0
	add	x2, x0, 64
	sub	x3, x1, #16
	lsr	x4, x3, 4
	add	x4, x2, x4, lsl 6
	mov	x2, x0
	mov	v25.16b, v26.16b
	mov	v24.16b, v26.16b
	mov	v31.16b, v26.16b
	.p2align 3,,7
.L3:
	ldp	q27, q28, [x2]
	ldp	q29, q30, [x2, 32]
	add	x2, x2, 64
	uadalp	v31.2d, v27.4s
	uadalp	v24.2d, v28.4s
	uadalp	v25.2d, v29.4s
	uadalp	v26.2d, v30.4s
	cmp	x2, x4
	bne	.L3
	add	v30.2d, v31.2d, v24.2d
	and	x3, x3, -16
	add	x3, x3, 16
	add	v30.2d, v30.2d, v25.2d
	add	v30.2d, v30.2d, v26.2d
	addp	d30, v30.2d
.L2:
	cmp	x1, x3
	bls	.L1
	sub	x5, x1, x3
	sub	x2, x5, #1
	cmp	x2, 2
	bls	.L5
	add	x2, x0, x3, lsl 2
	lsr	x4, x5, 2
	movi	v31.4s, 0
	add	x4, x2, x4, lsl 4
	.p2align 3,,7
.L6:
	ldr	q29, [x2], 16
	uaddw	v31.2d, v31.2d, v29.2s
	uaddw2	v31.2d, v31.2d, v29.4s
	cmp	x2, x4
	bne	.L6
	addp	d31, v31.2d
	tst	x5, 3
	add	d30, d30, d31
	beq	.L1
	and	x5, x5, -4
	add	x3, x3, x5
.L5:
	ldr	w4, [x0, x3, lsl 2]
	add	x2, x3, 1
	lsl	x5, x3, 2
	fmov	d31, x4
	add	d30, d30, d31
	cmp	x1, x2
	bls	.L1
	add	x0, x0, x5
	add	x3, x3, 2
	ldr	w2, [x0, 4]
	fmov	d31, x2
	add	d30, d30, d31
	cmp	x1, x3
	bls	.L1
	ldr	w0, [x0, 8]
	fmov	d31, x0
	add	d30, d30, d31
.L1:
	fmov	x0, d30
	ldp	x29, x30, [sp], 16
	.cfi_remember_state
	.cfi_restore 30
	.cfi_restore 29
	.cfi_def_cfa_offset 0
	ret
	.p2align 2,,3
.L9:
	.cfi_restore_state
	movi	v30.2d, #0
	mov	x3, 0
	b	.L2
	.cfi_endproc
.LFE3916:
	.size	sum_neon4, .-sum_neon4
	.ident	"GCC: (GNU) 14.3.0"
	.section	.note.GNU-stack,"",@progbits
