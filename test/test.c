#include <stdio.h>


void blah(int c)
{
        char body[1024];
        for (int j = 0; j < 1024; j++) {
                for (int y = 0; y < c; y+=2) {
                        printf("%i\n", y * j);
                }
                body[j] = j;
        }
}


int main()
{
        int i = 0;
        for (i = 0; i < 10; i++) {
                printf("hello world!\n");
                blah(i);
        }
}
