	.arch armv8-a
	.file	"kernels.c"
	.text
	.align	2
	.p2align 4,,15
	.global	scan_sum
	.type	scan_sum, %function
scan_sum:
.LFB0:
	.cfi_startproc
	stp	x29, x30, [sp, -16]!
	.cfi_def_cfa_offset 16
	.cfi_offset 29, -16
	.cfi_offset 30, -8
	mov	x29, sp
	cbz	x1, .L7
	sub	x2, x1, #1
	cmp	x2, 2
	bls	.L8
	lsr	x3, x1, 1
	movi	v31.4s, 0
	add	x3, x0, x3, lsl 4
	mov	x2, x0
	.p2align 3,,7
.L4:
	ldr	q30, [x2], 16
	add	v31.2d, v31.2d, v30.2d
	cmp	x2, x3
	bne	.L4
	addp	d31, v31.2d
	and	x2, x1, -2
	tbz	x1, 0, .L1
.L3:
	ldr	d30, [x0, x2, lsl 3]
	add	x3, x2, 1
	lsl	x4, x2, 3
	add	d31, d31, d30
	cmp	x1, x3
	bls	.L1
	add	x0, x0, x4
	add	x2, x2, 2
	ldr	d30, [x0, 8]
	add	d31, d31, d30
	cmp	x1, x2
	bls	.L1
	ldr	x0, [x0, 16]
	fmov	d30, x0
	add	d31, d31, d30
.L1:
	fmov	x0, d31
	ldp	x29, x30, [sp], 16
	.cfi_remember_state
	.cfi_restore 30
	.cfi_restore 29
	.cfi_def_cfa_offset 0
	ret
	.p2align 2,,3
.L7:
	.cfi_restore_state
	movi	v31.2d, #0
	ldp	x29, x30, [sp], 16
	.cfi_remember_state
	.cfi_restore 30
	.cfi_restore 29
	.cfi_def_cfa_offset 0
	fmov	x0, d31
	ret
.L8:
	.cfi_restore_state
	movi	v31.2d, #0
	mov	x2, 0
	b	.L3
	.cfi_endproc
.LFE0:
	.size	scan_sum, .-scan_sum
	.align	2
	.p2align 4,,15
	.global	chase_cycle
	.type	chase_cycle, %function
chase_cycle:
.LFB1:
	.cfi_startproc
	stp	x29, x30, [sp, -16]!
	.cfi_def_cfa_offset 16
	.cfi_offset 29, -16
	.cfi_offset 30, -8
	mov	x29, sp
	cbz	x1, .L18
	mov	x3, x0
	mov	x2, 0
	mov	x0, 0
	.p2align 3,,7
.L17:
	add	x2, x2, 1
	lsl	x0, x0, 7
	ldr	x0, [x3, x0]
	cmp	x1, x2
	bne	.L17
	ldp	x29, x30, [sp], 16
	.cfi_remember_state
	.cfi_restore 30
	.cfi_restore 29
	.cfi_def_cfa_offset 0
	ret
	.p2align 2,,3
.L18:
	.cfi_restore_state
	mov	x0, 0
	ldp	x29, x30, [sp], 16
	.cfi_restore 30
	.cfi_restore 29
	.cfi_def_cfa_offset 0
	ret
	.cfi_endproc
.LFE1:
	.size	chase_cycle, .-chase_cycle
	.ident	"GCC: (GNU) 14.3.0"
	.section	.note.GNU-stack,"",@progbits
