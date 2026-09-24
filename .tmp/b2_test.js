
const _els={};
function mkEl(id){ const ctx={canvas:null,fillStyle:'',strokeStyle:'',lineWidth:1,
  fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},clearRect(){}};
  const el={id:id,width:0,height:0,getContext:()=>ctx}; ctx.canvas=el; return el; }
global.document={getElementById:(id)=>{ if(!_els[id])_els[id]=mkEl(id); return _els[id]; }};

// ── 真实字模数据（由 BDF 提取，硬编码嵌入以保证离线可看）──
const RAW = {
  "啊": ["0000","0000","1DE0","F420","B420","BBA0","B6A0","B6A0","F7A0","1C20","1020","1020","10E0","0000","0000","0000"],
  "阿": ["0000","0000","F7E0","9040","A040","C740","A540","9540","9740","F040","8040","8040","81C0","0000","0000","0000"],
  "埃": ["0000","0000","2200","2440","2FE0","F000","2400","27C0","2900","3FE0","C280","0440","1820","0000","0000","0000"],
  "挨": ["0000","0000","2100","2240","F7E0","2020","2400","37C0","E900","3FE0","2280","2440","7820","0000","0000","0000"]
};
const CHARS = ["啊","阿","埃","挨"];

// 真实日版假名字模（font0 @0x081B3AAC, 1bpp 8×16）—— 用于对照证明"原生就是8×16"
const KANA = {
  "あ": ["0000","0000","0020","7F20","88C0","88A0","88A0","88A0","88A0","7900","0100","8100","8180","8080","7F00","0000"],
  "な": ["1F00","0A80","7FE0","0800","7400","5400","9500","BF00","2400","2400","2200","2200","4300","4C00","F000","0000"]
};

// 把十六进制行数据转成像素矩阵 [row][col]
function toMatrix(rows, w){
  const out=[];
  for(const r of rows){
    const v = parseInt(r,16);
    const bits=[];
    for(let b=0;b<w;b++) bits.push((v>>(w-1-b))&1);
    out.push(bits);
  }
  return out;
}

// 1bpp 8 宽 → 16 宽矩阵（左对齐，用于假名对照）
function kanaMatrix(rows){
  const m=[];
  for(const r of rows){
    const v=parseInt(r,16), bits=[];
    for(let b=0;b<8;b++) bits.push((v>>(7-b))&1);
    while(bits.length<16) bits.push(0);
    m.push(bits);
  }
  return m;
}

const PXU = 3.2;   // 每像素放大倍数

// 通用绘制：把 chars 按给定「cell 宽 × 高」摆放，blitW 之外标红
function render(cvId, chars, cw, ch, blitW, opt){
  opt = opt||{};
  const cv=document.getElementById(cvId); if(!cv) return;
  const ctx=cv.getContext('2d'), PX=PXU, n=chars.length;
  cv.width=n*cw*PX+2; cv.height=ch*PX+2;
  ctx.fillStyle='#f8f8f0'; ctx.fillRect(0,0,cv.width,cv.height);
  chars.forEach((ch_,i)=>{
    const m = RAW[ch_] ? toMatrix(RAW[ch_],16) : (KANA[ch_] ? kanaMatrix(KANA[ch_]) : null);
    if(!m) return;
    for(let y=0;y<ch;y++)for(let x=0;x<cw;x++){
      if(y>=m.length || x>=m[y].length) continue;
      if(!m[y][x]) continue;
      let col='#1a1a1a';
      if(blitW!=null && x>=blitW){
        col = opt.loss ? '#e8a0a0' : '#c0392b';   // loss=浅红(丢失) / 否则红(溢出被覆盖)
      }
      ctx.fillStyle=col;
      ctx.fillRect(1+(i*cw+x)*PX, 1+y*PX, PX,PX);
    }
    // 8px 边界虚线
    if(opt.mark && blitW!=null && blitW<cw){
      ctx.strokeStyle='#2980b9'; ctx.lineWidth=2;
      ctx.beginPath(); ctx.moveTo(1+(i*cw+blitW)*PX,1);
      ctx.lineTo(1+(i*cw+blitW)*PX, cv.height-1); ctx.stroke();
    }
  });
  // tile 横线
  if(opt.grid){
    ctx.strokeStyle='rgba(41,128,185,.55)'; ctx.lineWidth=1;
    for(let y=opt.grid;y<ch;y+=opt.grid){
      ctx.beginPath(); ctx.moveTo(1,y*PX+1); ctx.lineTo(cv.width-1,y*PX+1); ctx.stroke();
    }
  }
}


  // 方案1：压到 8 宽（无溢出，但右 3 列丢失且不标红——这是"设计如此"）
  render('c1', CHARS, 8, 16, null, {grid:8});

  // 方案2：16 宽，>8 部分标红（会溢出覆盖下一字）
  render('c2', CHARS, 16, 16, 8, {});

  // 方案3：12 宽，>8 部分浅红（被 blit 丢弃）+ 8px 蓝边界
  render('c3', CHARS, 12, 16, 8, {loss:true, mark:true});

  // 方案5：8 宽 × 16 高（原生推荐）
  render('c5', CHARS, 8, 16, null, {grid:8});

  // 方案4：12 宽完整（理想）
  render('c4', CHARS, 12, 16, null, {});

  // 假名对照：日版原生 8 宽 × 16 高
  render('c6', Object.keys(KANA), 8, 16, null, {grid:8});

console.log('--- render results ---');
for(const k of ['c1','c2','c3','c4','c5','c6']){
  if(!_els[k] || !_els[k].width){ console.log(k,'NOT RENDERED'); continue; }
  console.log(k,'w='+_els[k].width,'h='+_els[k].height);
}
console.log('OK');
