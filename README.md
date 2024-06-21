# LoLMaybe

A test project to see if LLMs can work with decompiler output to come up with
slightly better new variable names.

Remember seeing some posts where people talked about this, going as far as a
ghidra implementation IIRC.
Just wanted to see myself how well the concept worked.

Current view is that it doesn't work that well with the 7B models I've tested.
Handles the variables introduced as part of the compilation process badly.

Was a bit a nightmare to get a decent output format from the LLM, but seems
Langchain works pretty well.

Meant to be used via piping output from r2ghidra to this script.

Uses local models via ollama.

## Usage

To test it:
```
make # compile the testcase
python3 script.py --filename ./test/out-blah.c
```

See the `./test/r2script` script to on how to get output.

## Sample

Decompiled output from r2ghidra of `blah()` in `./test/test.c`
```c
void sym.blah(int32_t param_1)
{
    int32_t iVar1;
    int32_t iVar2;
    uchar *puVar3;
    int64_t in_FS_OFFSET;
    uchar auStack_438 [12];
    int32_t iStack_42c;
    int32_t iStack_420;
    int32_t iStack_41c;
    uchar auStack_418 [1032];
    int64_t iStack_10;

    puVar3 = *0x20 + -0x438;
    iStack_10 = *(in_FS_OFFSET + 0x28);
    iStack_42c = param_1;
    for (iStack_420 = 0; iStack_420 == 0x3ff || SBORROW4(iStack_420, 0x3ff) != iStack_420 + -0x3ff < 0;
        iStack_420 = iStack_420 + 1) {
        for (iStack_41c = 0; iStack_41c < iStack_42c; iStack_41c = iStack_41c + 2) {
            iVar1 = iStack_41c;
            iVar2 = iStack_420;
            *(puVar3 + -8) = 0x11e8;
            sym.imp.printf(0x2004, iVar1 * iVar2);
            puVar3 = puVar3;
        }
        (&stack0xfffffffffffffbe8)[iStack_420] = iStack_420;
    }
    if (iStack_10 != *(in_FS_OFFSET + 0x28)) {
    // WARNING: Subroutine does not return
        *(puVar3 + -8) = 0x123c;
        sym.imp.__stack_chk_fail();
    }
    return;
}
```

Renamed:
```c
/* param_1  -> inputValue */
/* iVar1  -> multiplicand */
/* iVar2  -> index */
/* puVar3  -> bufferPointer */
/* in_FS_OFFSET  -> stackGuardOffset */
/* auStack_438  -> stackBuffer */
/* iStack_42c  -> numElements */
/* iStack_420  -> loopCounter */
/* iStack_41c  -> indexMultiplier */
/* auStack_418  -> stackBuffer_0 */
/* iStack_10  -> initialStackPointer */
void blah(int32_t inputValue)
{
  int32_t multiplicand;
  int32_t index;
  uchar *bufferPointer;
  int64_t stackGuardOffset;
  uchar stackBuffer[12];
  int32_t numElements;
  int32_t loopCounter;
  int32_t indexMultiplier;
  uchar stackBuffer_0[1032];
  int64_t initialStackPointer;
  bufferPointer = (*0x20) + (-0x438);
  initialStackPointer = *(stackGuardOffset + 0x28);
  numElements = inputValue;
  for (loopCounter = 0; (loopCounter == 0x3ff) || (SBORROW4(loopCounter, 0x3ff) != ((loopCounter + (-0x3ff)) < 0)); loopCounter = loopCounter + 1)
  {
    for (indexMultiplier = 0; indexMultiplier < numElements; indexMultiplier = indexMultiplier + 2)
    {
      multiplicand = indexMultiplier;
      index = loopCounter;
      *(bufferPointer + (-8)) = 0x11e8;
      printf(0x2004, multiplicand * index);
      bufferPointer = bufferPointer;
    }

    (&stack0xfffffffffffffbe8)[loopCounter] = loopCounter;
  }

  if (initialStackPointer != (*(stackGuardOffset + 0x28)))
  {
    *(bufferPointer + (-8)) = 0x123c;
    __stack_chk_fail();
  }
  return;
}
```

So kinda okish, for this easy function.

## License

MIT
