	.arch armv8-a
	.file	"sum_plain.c"
	.text
	.align	2
	.p2align 4,,11
	.global	sum_o2
	.type	sum_o2, %function
sum_o2:
.LFB0:
	.cfi_startproc
	stp	x29, x30, [sp, -16]!
	.cfi_def_cfa_offset 16
	.cfi_offset 29, -16
	.cfi_offset 30, -8
	mov	x29, sp
	cbz	x1, .L4
	mov	x2, x0
	mov	x0, 0
	add	x3, x2, x1, lsl 2
	.p2align 3,,7
.L3:
	ldr	w1, [x2], 4
	add	x0, x0, x1
	cmp	x2, x3
	bne	.L3
	ldp	x29, x30, [sp], 16
	.cfi_remember_state
	.cfi_restore 30
	.cfi_restore 29
	.cfi_def_cfa_offset 0
	ret
	.p2align 2,,3
.L4:
	.cfi_restore_state
	mov	x0, 0
	ldp	x29, x30, [sp], 16
	.cfi_restore 30
	.cfi_restore 29
	.cfi_def_cfa_offset 0
	ret
	.cfi_endproc
.LFE0:
	.size	sum_o2, .-sum_o2
	.ident	"GCC: (GNU) 14.3.0"
	.section	.note.GNU-stack,"",@progbits
