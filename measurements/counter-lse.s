	.arch armv8.2-a+crc
	.file	"counter.cpp"
	.text
	.align	2
	.p2align 4,,15
	.global	increment_counter
	.type	increment_counter, %function
increment_counter:
.LFB314:
	.cfi_startproc
	stp	x29, x30, [sp, -16]!
	.cfi_def_cfa_offset 16
	.cfi_offset 29, -16
	.cfi_offset 30, -8
	mov	x29, sp
	cbz	x1, .L1
	mov	x2, 0
	mov	x3, 1
	.p2align 3,,7
.L3:
	ldadd	x3, x4, [x0]
	add	x2, x2, 1
	cmp	x1, x2
	bne	.L3
.L1:
	ldp	x29, x30, [sp], 16
	.cfi_restore 30
	.cfi_restore 29
	.cfi_def_cfa_offset 0
	ret
	.cfi_endproc
.LFE314:
	.size	increment_counter, .-increment_counter
	.ident	"GCC: (GNU) 14.3.0"
	.section	.note.GNU-stack,"",@progbits
