/*
Adapted from Dopamine 3.0.10 forkfix and jbclient_mach (commit 1a54e76).
MIT License

Copyright (c) 2023-2024 Lars Fröder (opa334)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

*/
.text

.align 4

.global _macws_forkfix_raw_fork
_macws_forkfix_raw_fork:
#ifdef __arm64e__
	pacibsp
#endif
	stp x29, x30, [SP, #-0x10]!
	mov x29, sp
	mov x16, #2
	svc 0x80
	b.cs _macws_forkfix_raw_fork_err
	cbz x1, _macws_forkfix_raw_fork_end
	mov w0, #0
	adrp x9, __current_pid@GOTPAGE
	ldr x9, [x9, __current_pid@GOTPAGEOFF]
	str w0, [x9]
	b _macws_forkfix_raw_fork_end

_macws_forkfix_raw_fork_err:
	bl _cerror
	mov w0, #-1

_macws_forkfix_raw_fork_end:
	mov sp, x29
	ldp x29, x30, [SP],#0x10
#ifdef __arm64e__
	retab
#else
    ret
#endif

.global _macws_forkfix_raw_read
_macws_forkfix_raw_read:
	mov x16, #3
	svc 0x80
	ret

.global _macws_forkfix_raw_write
_macws_forkfix_raw_write:
	mov x16, #4
	svc 0x80
	ret

.global _macws_forkfix_raw_close
_macws_forkfix_raw_close:
	mov x16, #6
	svc 0x80
	ret

.global _macws_forkfix_raw_exit
_macws_forkfix_raw_exit:
    mov x16, #1
    svc 0x80
    b _macws_forkfix_raw_exit
