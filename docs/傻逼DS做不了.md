禁止【wait】、【Let me reconsider】这种思维，出现问题，则按流水线跑一边确认
需要走LLM。可以适当删掉1-2条译文触发
接下来是各阶段新增内容
一：translate
1、texts.json（不存在时，视为空，不要老是自己新增空的texts.json，你TM手贱创建多少次了） / texts.txt（\n切割） => LLM
2、LLM => texts_trabsated.json
3、texts.json  + texts_trabsated.json => translated.build.json
4、texts_trabsated.json => texts_trabsated.asm
5、其他流程照旧（由于 texts.json 不存在，因此生成空的 translated.build.json，实际上ROM没有改动字节）

二：hook
【原有内容】
if f9
 return f9
return jp
【改为】
if f9
 return f9
if has_cache(jp)
 return f9(get_cache(jp))
return jp
禁止手贱删掉F900、F980逻辑，我又没说废掉之前链路

三：
gdb_patcher.py
1、将 InitTextPrinter 的逻辑直接改为 PrintNextChar
2、一样
if (has_cache(jp))
 console.log(jp)
 return 
console.log(jp)
// 写入到 work/{gameId}/texts.txt
append2File(work/{gameId}/texts.txt, jp)