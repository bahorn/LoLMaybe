
build:
	$(CC) -O0 ./test.c -o ./out.bin
	radare2 -qq -i ./r2script ./out.bin

clean:
	-rm out.bin
	-rm out-blah.c
	-rm out-main.c
