import zstandard, io, json
f=r"C:\Users\Administrator\.dsh\sessions\--C-code-GBA-Rom-Translator--\session-420dbb06-6e20-46b5-9d79-685250b1d8bf\session.v4.jsonl.zstd"
d=zstandard.ZstdDecompressor()
with open(f,'rb') as fh:
    data=d.stream_reader(fh).read()
print(len(data))
open(r"C:\code\GBA-Rom-Translator\out\sess_420dbb06.jsonl",'wb').write(data)
