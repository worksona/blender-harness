/* HAVEN REALTIME / self-contained WebGL2 architectural renderer.
 * No remote modules, models, textures, or shader services required.
 * Geometry is programmatic and lighting follows verified Home Assistant state.
 */
function createRealtimeModel(){
 const host=$('#viewport'), shell=host.parentElement;
 const canvas=document.createElement('canvas');canvas.className='haven-realtime-canvas';canvas.setAttribute('aria-label','Interactive 3D home. Drag to orbit; scroll to zoom; click a room to inspect devices.');
 const gl=canvas.getContext('webgl2',{antialias:true,alpha:true,depth:true,powerPreference:'high-performance',stencil:false});
 if(!gl)throw new Error('WebGL2 is unavailable.');
 host.append(canvas);host.style.pointerEvents='auto';
 const V=(x=0,y=0,z=0)=>[x,y,z],sub=(a,b)=>a.map((x,i)=>x-b[i]),add=(a,b)=>a.map((x,i)=>x+b[i]),dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],unit=(v)=>{const d=Math.hypot(...v)||1;return v.map(x=>x/d)},scale=(a,s)=>a.map(x=>x*s);
 const mult=(a,b)=>{const o=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)o[c*4+r]+=a[k*4+r]*b[c*4+k];return o};
 function lookAt(eye,at,up=[0,1,0]){let z=unit(sub(eye,at)),x=unit(cross(up,z)),y=cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1]);}
 function perspective(fov,asp,n,f){const q=1/Math.tan(fov/2);return new Float32Array([q/asp,0,0,0,0,q,0,0,0,0,(f+n)/(n-f),-1,0,0,2*f*n/(n-f),0]);}
 function ortho(l,r,b,t,n,f){return new Float32Array([2/(r-l),0,0,0,0,2/(t-b),0,0,0,0,-2/(f-n),0,-(r+l)/(r-l),-(t+b)/(t-b),-(f+n)/(f-n),1]);}
 const hex=h=>[(h>>16&255)/255,(h>>8&255)/255,(h&255)/255];
 const PAL={ivory:0xeadfce,wall:0xcac4bb,clay:0xa7907b,oak:0xa67d5b,oak2:0x8e6a52,walnut:0x5a4039,cream:0xdbd4c7,stone:0xb8b5a9,marble:0xd1cec6,bronze:0xb58b54,gold:0xf6c787,glass:0xb5daea,blue:0x54697a,ink:0x202932,screen:0x162d3b,tile:0xbac9c9,moss:0x687a61,forest:0x415846,plant:0x446849,leaf:0x789a71,rug:0xa8a69a,linen:0xe5e0d3,rust:0xa7705c,black:0x34373a,water:0x8cb6c0,ceiling:0xfcdfaa};
 const MAT={plain:0,wood:1,marble:2,fabric:3,tile:4,rug:5,glow:6,leaf:7,metal:8,stone:9,glass:10,blind:11,screen:12,fan:13};
 const solid={p:[],i:[]},transparent={p:[],i:[]},emissive={p:[],i:[]};const pstride=11;
 function buildVertex(out,pos,n,c,type,rough,met,em){out.p.push(pos[0],pos[1],pos[2],n[0],n[1],n[2],...hex(c),type,Math.min(1,Math.max(0,rough)),Math.min(1,Math.max(0,met)),em||0)}
 // 13 floats per vertex: XYZ / normal / albedo / material type / rough / metallic / emissive
 const STRIDE=13;
 function quad(out,a,b,c,d,col,type=0,rough=.83,met=0,em=0,normal=null){let n=normal||unit(cross(sub(b,a),sub(c,a)));let s=out.p.length/STRIDE;for(let pos of [a,b,c,d])buildVertex(out,pos,n,col,type,rough,met,em);out.i.push(s,s+1,s+2,s,s+2,s+3);}
 function tri(out,a,b,c,col,type=0,rough=.83,met=0,em=0){const n=unit(cross(sub(b,a),sub(c,a)));let s=out.p.length/STRIDE;for(let pos of [a,b,c])buildVertex(out,pos,n,col,type,rough,met,em);out.i.push(s,s+1,s+2)}
 function box(x,y,z,w,h,d,col=PAL.wall,type=0,opts={}){
  const target=opts.glass?transparent:opts.em?emissive:solid,rot=opts.rot||0,r=opts.round||0,rough=opts.rough??.82,met=opts.metal??0,em=opts.em||0;
  const rx=(point)=>[point[0]*Math.cos(rot)-point[2]*Math.sin(rot)+x,point[1]+y,point[0]*Math.sin(rot)+point[2]*Math.cos(rot)+z];
  let hs=[w/2,h/2,d/2];const coords=[[ -1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]];
  // Bevelled edges with per-pixel smoothed normals. Every face subdivides only near rounded boundaries.
  for(let axis=0;axis<3;axis++)for(let sign of [-1,1]){
   let a=(axis+1)%3,b=(axis+2)%3,ha=hs[a],hb=hs[b],rad=Math.min(r,Math.min(...hs)*.8);
   const cuts=(half)=>rad>0?[-half,-half+rad*.30,-half+rad,half-rad,half-rad*.30,half]:[-half,half];
   const us=cuts(ha),vs=cuts(hb);const side=target.p.length/STRIDE;
   for(let i=0;i<us.length;i++)for(let j=0;j<vs.length;j++){
    const pos=[0,0,0];pos[axis]=sign*hs[axis];pos[a]=us[i];pos[b]=vs[j];
    let normal=[0,0,0];normal[axis]=sign;const orig=[...pos];
    if(rad){const inner=pos.map((v,k)=>Math.max(-hs[k]+rad,Math.min(hs[k]-rad,v)));const offset=sub(pos,inner);const v=unit(offset);for(let k=0;k<3;k++){pos[k]=inner[k]+v[k]*rad;normal[k]=v[k];}}
    const world=rx(pos);const nn=[normal[0]*Math.cos(rot)-normal[2]*Math.sin(rot),normal[1],normal[0]*Math.sin(rot)+normal[2]*Math.cos(rot)];buildVertex(target,world,nn,col,type,rough,met,em);
   }
   for(let i=0;i<us.length-1;i++)for(let j=0;j<vs.length-1;j++){
    const a1=side+i*vs.length+j,b1=side+(i+1)*vs.length+j,c1=b1+1,d1=a1+1;
    if((axis===1?-sign:sign)>0)target.i.push(a1,b1,c1,a1,c1,d1);else target.i.push(a1,c1,b1,a1,d1,c1);
   }
  }
 }
 function cyl(x,y,z,r,h,col=PAL.oak,type=MAT.wood,options={}){const seg=options.seg||18,upper=options.top??r,rough=options.rough??.8,metal=options.metal||0,em=options.em||0,out=em?emissive:options.glass?transparent:solid,rad=options.rot||0;
  const rr=(a)=>[x+Math.cos(a+rad)*r,z+Math.sin(a+rad)*r],ru=(a)=>[x+Math.cos(a+rad)*upper,z+Math.sin(a+rad)*upper];
  for(let k=0;k<seg;k++){const a=k/seg*Math.PI*2,b=(k+1)/seg*Math.PI*2,v=rr(a),q=rr(b),t=ru(a),s=ru(b),nn=unit([Math.cos((a+b)/2+rad),(r-upper)/h,Math.sin((a+b)/2+rad)]);
   quad(out,[...v.slice(0,1),y-h/2,v[1]],[...q.slice(0,1),y-h/2,q[1]],[s[0],y+h/2,s[1]],[t[0],y+h/2,t[1]],col,type,rough,metal,em,nn);
   tri(out,[x,y+h/2,z],[t[0],y+h/2,t[1]],[s[0],y+h/2,s[1]],col,type,rough,metal,em);
   tri(out,[x,y-h/2,z],[q[0],y-h/2,q[1]],[v[0],y-h/2,v[1]],col,type,rough,metal,em);
  }
 }
 function orb(x,y,z,rx,ry,rz,color=PAL.leaf,type=MAT.leaf,options={}){const out=options.em?emissive:solid,rough=options.rough??.87,met=options.metal||0,em=options.em||0,rot=options.rot||0,lat=9,lon=13;const s=out.p.length/STRIDE;
  for(let i=0;i<=lat;i++)for(let j=0;j<=lon;j++){const a=i/lat*Math.PI,b=j/lon*Math.PI*2;let xx=Math.sin(a)*Math.cos(b),zz=Math.sin(a)*Math.sin(b),yy=Math.cos(a);const nx=xx*Math.cos(rot)-zz*Math.sin(rot),nz=xx*Math.sin(rot)+zz*Math.cos(rot);buildVertex(out,[x+nx*rx,y+yy*ry,z+nz*rz],unit([nx/rx,yy/ry,nz/rz]),color,type,rough,met,em)}
  for(let i=0;i<lat;i++)for(let j=0;j<lon;j++){let a=s+i*(lon+1)+j,b=a+lon+1;out.i.push(a,b,a+1,b,b+1,a+1)}
 }
 function rod(a,b,r,color=PAL.bronze,type=MAT.metal,opts={}){let dir=sub(b,a),len=Math.hypot(...dir),up=unit(dir),right=unit(cross(Math.abs(up[1])>.95?[1,0,0]:[0,1,0],up)),z=cross(right,up),seg=opts.seg||10,out=opts.em?emissive:solid;for(let k=0;k<seg;k++){let t=k*2*Math.PI/seg,u=(k+1)*2*Math.PI/seg;const loc=(p,a)=>add(p,add(scale(right,Math.cos(a)*r),scale(z,Math.sin(a)*r)));quad(out,loc(a,t),loc(a,u),loc(b,u),loc(b,t),color,type,opts.rough??.38,opts.metal??.7,opts.em||0,unit(add(scale(right,Math.cos((t+u)/2)),scale(z,Math.sin((t+u)/2)))));}}
 function ring(x,y,z,r,thick,col=PAL.bronze,opts={}){const seg=32,parts=7,out=opts.em?emissive:solid;for(let i=0;i<seg;i++){const a=i*Math.PI*2/seg,b=(i+1)*Math.PI*2/seg;for(let j=0;j<parts;j++){const c=j*Math.PI*2/parts,d=(j+1)*Math.PI*2/parts;const p=(v,u)=>[(r+Math.cos(u)*thick)*Math.cos(v)+x,y+Math.sin(u)*thick,(r+Math.cos(u)*thick)*Math.sin(v)+z];quad(out,p(a,c),p(b,c),p(b,d),p(a,d),col,opts.em?MAT.glow:MAT.metal,.26,.6,opts.em||0);}}}
 function rug(x,z,w,d,color=PAL.rug){box(x,.075,z,w,.04,d,color,MAT.rug,{round:.024,rough:1});}
 function sofaSoft(x,y,z,w,h,d,color=PAL.cream,rot=0){box(x,y,z,w,h,d,color,MAT.fabric,{round:.10,rough:1,rot});}
 function furnitureLegs(x,z,w,d,h,y=.34,color=PAL.walnut){for(let a of [-1,1])for(let b of [-1,1])box(x+a*w*.4,y,z+b*d*.40,.055,h,.055,color,MAT.wood,{round:.018});}
 function pot(x,z,k=1){cyl(x,.24*k,z,.19*k,.36*k,PAL.clay,MAT.stone,{top:.25*k,seg:14});cyl(x,.436*k,z,.215*k,.036*k,PAL.ivory,MAT.stone);for(let i=0;i<9;i++){const a=i*2.399,r=.08*k+(i%3)*.07*k;let yy=.56*k+(i%5)*.115*k;rod([x,.41*k,z],[x+Math.cos(a)*r,yy,z+Math.sin(a)*r],.014*k,PAL.forest,MAT.leaf,{metal:0});orb(x+Math.cos(a)*r,yy,z+Math.sin(a)*r,.12*k,.22*k,.065*k,i%2?PAL.leaf:PAL.plant,MAT.leaf,{rot:a});}}
 const bulbs=[];function lum(room,x,y,z,power=1){const id=rooms.findIndex(r=>r.id===room);bulbs.push({room,id,x,y,z,power});orb(x,y,z,.065,.065,.065,PAL.gold,MAT.glow,{em:2.7});}
 function lamp(room,x,z,y=1.25){cyl(x,.09,z,.21,.07,PAL.bronze,MAT.metal,{metal:.75});rod([x,.12,z],[x,y-.14,z],.022,PAL.bronze);cyl(x,y-.11,z,.25,.22,PAL.ivory,MAT.fabric,{top:.13});lum(room,x,y-.03,z,.9);}
 // Floating limestone architecture / beveled metal understructure and warm inset reveal.
 box(0,-.41,0,14.83,.15,10.82,0x252b2d,MAT.metal,{round:.06,metal:.7});
 box(0,-.29,0,14.65,.20,10.66,0x6c6155,MAT.stone,{round:.08});
 box(0,-.173,0,14.54,.07,10.58,PAL.bronze,MAT.metal,{rough:.27,metal:.79});
 box(0,-.09,0,14.45,.12,10.48,PAL.stone,MAT.stone,{round:.04});
 // Studio cyclorama catches the cast shadows of the floating cutaway.
 box(0,-.80,0,46,.17,37,0x293039,MAT.stone,{rough:1});
 for(let n=0;n<12;n++){let x=-13.3+n*2.4;box(x,-.70,9.0,.74,.06,.74,n%2?0x535b5c:0x46494b,MAT.stone,{round:.06,rot:Math.sin(n*9)*.28});}
 // Seven architectural rooms. Flooring planks follow global world coordinates.
 for(const r of rooms){box(r.x,-.015,r.z,r.w,.12,r.d,['bath','kitchen'].includes(r.id)?(r.id==='bath'?PAL.tile:PAL.marble):PAL.oak,MAT[['bath','kitchen'].includes(r.id)?(r.id==='bath'?'tile':'marble'):'wood'],{rough:r.id==='bath'?.42:.76});}
 // Boundary walls are solid but selectively cut away for camera visibility.
 const wall=(x,z,w,d,h=1.8,color=PAL.wall)=>box(x,h/2,z,w,h,d,color,MAT.stone,{rough:.92});
 wall(0,-5.17,14.50,.17,2.45,PAL.ivory);wall(-7.18,0,.18,10.30,2.08,PAL.ivory);wall(7.18,0,.18,10.3,2.08,PAL.ivory);wall(0,5.17,14.40,.13,.23,PAL.ivory);
 const vw=(x,z1,z2,h=1.36)=>wall(x,(z1+z2)/2,.105,Math.abs(z2-z1),h,PAL.ivory);
 const hw=(z,x1,x2,h=1.36)=>wall((x1+x2)/2,z,Math.abs(x2-x1),.105,h,PAL.ivory);
 vw(-2.05,-5,-2.3);vw(-2.05,-.80,1.3);vw(-2.05,2.8,5.0,.85);vw(.83,-5,-2.45);vw(.83,-1.2,1.51);vw(.83,2.9,5.0,.91);vw(3.67,1.2,2.15);vw(3.67,3.45,5.0,1.04);
 hw(.19,-7,-5.2);hw(.19,-3.84,-2.05);hw(.19,-1.99,-.86);hw(.19,.19,.80);hw(1.18,.86,1.8);hw(1.18,2.78,5.05);hw(1.18,5.69,7.05);
 // Wainscoting, window frames, vertical trims and thresholds.
 for(const x of [-4.6,3.25]){const ww=x<0?2.75:2.8;box(x,1.11,-5.045,ww,1.24,.034,PAL.glass,MAT.glass,{glass:true});for(const dx of [-ww*.5,0,ww*.5])box(x+dx,1.18,-4.986,.035,1.45,.065,PAL.bronze,MAT.metal,{metal:.5});for(const yy of [.45,1.79])box(x,yy,-4.986,ww+.1,.055,.09,PAL.ivory,MAT.plain);box(x,.47,-4.79,ww+.14,.055,.28,PAL.marble,MAT.marble,{rough:.25});}
 for(let i=0;i<8;i++){box(-7.074,.08,-4.6+i*1.24,.03,.10,1.1,PAL.cream,MAT.stone);box(7.074,.08,-4.6+i*1.24,.03,.10,1.1,PAL.cream,MAT.stone)}
 // Sculptural furniture — living suite, six cushion composition, walnut table and credenza.
 rug(-4.64,2.64,3.75,2.9,0x95978d);
 sofaSoft(-5.61,.37,2.93,.92,.48,2.23,0xb3b0a4);sofaSoft(-4.75,.35,3.64,2.95,.50,.89,0xb3b0a4);
 sofaSoft(-5.88,.69,2.90,.22,.57,2.3,0xb3b0a4);sofaSoft(-4.75,.72,4.08,2.97,.66,.22,0xb3b0a4);
 for(const a of [-5.57,-4.77,-3.97])sofaSoft(a,.63,3.56,.71,.22,.68,PAL.cream);
 for(let i=0;i<3;i++)sofaSoft(-5.52,.70,2.18+i*.65,.48,.32,.14,0xb5b3aa,Math.sin(i)*.07);
 for(let i=0;i<3;i++){const colors=[PAL.rust,PAL.linen,PAL.moss];sofaSoft(-5.55+i*.69,.84,3.76,.44,.30,.16,colors[i],Math.sin(i*2)*.17);}
 box(-4.10,.34,2.34,1.54,.145,.87,PAL.walnut,MAT.wood,{round:.085,rough:.32});furnitureLegs(-4.10,2.34,1.4,.71,.32,.15);
 box(-2.47,.34,2.55,.33,.54,1.83,PAL.walnut,MAT.wood,{round:.035});box(-2.53,.88,2.55,.075,1.15,1.80,PAL.black,MAT.metal,{rough:.23,metal:.5});box(-2.577,.89,2.55,.018,1.04,1.66,PAL.screen,MAT.screen,{em:.14});
 for(let i=0;i<4;i++)box(-2.45,.36,1.87+i*.28,.036,.045,.20,PAL.bronze,MAT.metal,{metal:.8});
 for(let i=0;i<3;i++){box(-4.5,.47+i*.035,2.45,.44,.043,.29,[PAL.ivory,PAL.rust,PAL.blue][i],MAT.fabric,{round:.01,rot:.16});}cyl(-3.74,.53,2.25,.08,.20,PAL.ivory,MAT.marble,{top:.06});
 pot(-6.42,.80,.85);lamp('living',-3.03,4.22,1.21);lum('living',-4.43,1.75,2.4,.96);
 // Dining: wood pedestal table, sculpted seating, woven placemats, tableware and bespoke chandelier.
 rug(-4.49,-2.44,3.87,3.48,0x9d9080);
 cyl(-4.49,.68,-2.45,1.07,.14,PAL.walnut,MAT.wood,{seg:36});cyl(-4.49,.34,-2.45,.19,.55,PAL.walnut,MAT.wood,{top:.13});cyl(-4.49,.08,-2.45,.52,.10,PAL.walnut,MAT.wood,{seg:28});
 for(let i=0;i<4;i++){const a=i*Math.PI*.5,xx=-4.49+Math.cos(a)*1.56,zz=-2.45+Math.sin(a)*1.56;cyl(xx,.42,zz,.33,.13,PAL.clay,MAT.fabric,{seg:20});box(xx+Math.cos(a)*.21,.73,zz+Math.sin(a)*.21,.59,.60,.12,PAL.oak,MAT.wood,{rot:-a,round:.065});for(const q of [-1,1])rod([xx+q*.15,.37,zz],[xx+q*.15,.15,zz],.025,PAL.walnut,MAT.wood);}
 for(let i=0;i<4;i++){const a=i*Math.PI*.5,xx=-4.49+Math.sin(a)*.68,zz=-2.45+Math.cos(a)*.68;ring(xx,.764,zz,.155,.013,PAL.ivory);cyl(xx,.753,zz,.122,.017,PAL.linen,MAT.marble,{seg:24});box(xx+.18,.76,zz,.017,.013,.22,PAL.bronze,MAT.metal,{metal:.8});}
 ring(-4.49,1.71,-2.45,.45,.025,PAL.bronze);rod([-4.49,2.44,-2.45],[-4.49,1.7,-2.45],.012,PAL.bronze);lum('dining',-4.49,1.68,-2.45,1.36);pot(-6.42,-4.04,.79);
 // Kitchen: two slabs, glossy limestone counters, panels, chrome fixtures, hob and stools.
 box(-.63,.45,-4.47,2.43,.75,.59,PAL.cream,MAT.wood,{round:.035});box(-.63,.849,-4.47,2.57,.085,.73,PAL.marble,MAT.marble,{round:.022,rough:.21});
 for(let i=0;i<4;i++){const x=-1.53+i*.59;box(x,.45,-4.075,.018,.69,.03,PAL.clay,MAT.wood);box(x+.27,.49,-4.068,.25,.020,.035,PAL.bronze,MAT.metal,{metal:.8});}
 box(.40,.40,-2.84,.58,.72,2.57,PAL.cream,MAT.wood,{round:.022});box(.41,.78,-2.84,.68,.08,2.64,PAL.marble,MAT.marble,{rough:.20});
 box(-.62,.43,-2.02,1.77,.73,.89,PAL.walnut,MAT.wood,{round:.038});box(-.63,.835,-2.02,1.96,.09,1.04,PAL.marble,MAT.marble,{round:.032,rough:.17});
 for(let i=0;i<3;i++){const x=-1.26+i*.61;cyl(x,.34,-1.11,.29,.10,PAL.clay,MAT.fabric);rod([x,.15,-1.11],[x,.31,-1.11],.038,PAL.bronze);}
 for(let xx of [-.98,-.40])for(let zz of [-2.25,-1.84])ring(xx,.91,zz,.108,.012,PAL.black);
 box(-1.18,.894,-4.49,.50,.02,.32,0x657b81,MAT.metal,{metal:.85});rod([-1.2,.88,-4.52],[-1.2,1.18,-4.52],.017,PAL.bronze);rod([-1.2,1.18,-4.52],[-.97,1.18,-4.52],.018,PAL.bronze);
 for(let i=0;i<3;i++){box(-1.17+i*.48,1.63,-4.5,.40,.47,.44,PAL.cream,MAT.wood,{round:.025});box(-1.17+i*.48,1.33,-4.24,.24,.017,.027,PAL.bronze,MAT.metal,{metal:.6});}
 box(-.55,1.23,-4.14,2.23,.027,.065,PAL.gold,MAT.glow,{em:1.35});lum('kitchen',-.62,1.75,-2.18,1.11);lum('kitchen',-.62,1.62,-4.16,.9);
 // Bedroom: upholstered headboard, sculpted mattress, layered duvet and pillows, sideboards.
 rug(3.85,-1.66,4.55,4.40,0xc4b6a4);
 box(3.85,.48,-1.75,3.48,.52,3.47,PAL.walnut,MAT.wood,{round:.055});sofaSoft(3.86,.64,-1.76,3.30,.31,3.20,PAL.ivory);
 sofaSoft(3.86,.88,-3.31,3.51,1.08,.24,0x978d82);
 sofaSoft(3.86,.816,-1.21,3.25,.22,2.18,PAL.linen);sofaSoft(3.86,.84,-.20,3.20,.13,.57,PAL.clay);
 for(const x of [3.06,4.56]){sofaSoft(x,.86,-2.98,1.11,.24,.63,PAL.ivory);sofaSoft(x,.92,-2.62,.58,.27,.18,0xb8b0a0);}
 for(const x of [1.71,6.05]){box(x,.35,-3.26,.73,.61,.68,PAL.walnut,MAT.wood,{round:.04});box(x,.67,-3.26,.79,.055,.73,PAL.marble,MAT.marble,{rough:.28});lamp('bedroom',x,-3.27,1.10);}
 box(6.50,1.12,-1.27,.44,2.05,2.86,PAL.oak,MAT.wood,{round:.02});for(let i=0;i<4;i++)box(6.248,1.02,-2.26+i*.65,.025,1.73,.025,PAL.walnut,MAT.wood);
 pot(1.36,.56,.73);lum('bedroom',3.85,1.98,-2.0,.88);
 // Bathroom: wide bathtub, inset water, mirror, contemporary wall-mounted vanity and translucent shower.
 box(2.58,.42,2.87,1.05,.69,1.85,PAL.ivory,MAT.marble,{round:.17,rough:.17});box(2.57,.78,2.87,.81,.040,1.58,PAL.water,MAT.glass,{glass:true});
 box(1.39,.48,3.65,.64,.70,1.62,PAL.oak,MAT.wood,{round:.025});box(1.38,.85,3.65,.72,.065,1.74,PAL.marble,MAT.marble,{rough:.18});
 cyl(1.37,.917,3.66,.24,.06,PAL.ivory,MAT.marble,{seg:25});rod([1.37,.92,3.68],[1.37,1.15,3.68],.014,PAL.bronze);rod([1.37,1.15,3.68],[1.55,1.15,3.68],.014,PAL.bronze);
 box(1.02,1.50,3.66,.055,.85,1.30,0x819c9e,MAT.metal,{round:.035,rough:.12,metal:.81});
 box(3.43,1.10,2.77,.03,1.62,1.49,PAL.glass,MAT.glass,{glass:true});rod([3.38,.62,2.14],[3.38,1.79,2.14],.016,PAL.bronze);rod([3.38,1.78,2.14],[3.04,1.78,2.14],.016,PAL.bronze);cyl(3.02,1.77,2.14,.14,.031,PAL.bronze,MAT.metal,{metal:.8});
 for(let i=0;i<3;i++)box(1.86,1.0+i*.09,4.44,.44,.085,.46,i%2?PAL.clay:PAL.linen,MAT.fabric,{round:.035});lum('bath',1.56,1.88,3.76,.97);
 // Office: architect's desk, dual monitors, keycaps, desk chair, plants and shelves.
 rug(5.19,2.9,2.44,2.60,0x919e9d);
 box(5.15,.78,2.37,2.20,.12,.82,PAL.walnut,MAT.wood,{round:.046,rough:.35});furnitureLegs(5.15,2.37,2.17,.70,.77,.35,PAL.black);
 for(let i=0;i<2;i++){const x=4.78+i*.84;box(x,1.26,2.09,.83,.67,.067,PAL.black,MAT.metal,{round:.026,rough:.22,metal:.5});box(x,1.26,2.045,.72,.55,.012,i?0x283d4d:0x3d5963,MAT.glow,{em:.22});rod([x,.83,2.09],[x,1.0,2.09],.025,PAL.bronze);}
 box(5.14,.86,2.76,.80,.024,.22,0x78858a,MAT.metal,{metal:.6});for(let i=0;i<16;i++)box(4.77+i*.049,.877,2.76,.029,.009,.15,i%3?PAL.black:0x5c6a72,MAT.plain);
 cyl(5.25,.29,3.66,.38,.13,PAL.blue,MAT.fabric);rod([5.25,.14,3.66],[5.25,.73,3.66],.035,PAL.black);sofaSoft(5.25,.78,4.0,.74,.67,.16,PAL.blue);
 box(6.48,.89,4.12,.44,1.63,.69,PAL.oak,MAT.wood);for(let j=0;j<4;j++)box(6.46,.35+j*.35,4.1,.44,.035,.67,PAL.walnut,MAT.wood);
 for(let i=0;i<19;i++){const x=6.36+(i%4)*.085,y=.41+Math.floor(i/4)*.32;box(x,y,4.19,.06,.18+.04*Math.sin(i*3)**2,.26,[PAL.ivory,PAL.blue,PAL.rust,PAL.moss][i%4],MAT.fabric);}
 pot(3.98,4.29,.61);lamp('office',5.92,2.4,1.20);lum('office',5.22,1.86,3.25,.78);
 // Entryway: floating sideboard, coat hangers, framed wall art and sculptural greenery.
 rug(-.63,2.7,1.72,3.24,0xa58c7b);
 box(-1.28,.39,3.51,.63,.57,1.38,PAL.walnut,MAT.wood,{round:.037});box(-1.28,.70,3.51,.68,.055,1.45,PAL.marble,MAT.marble,{rough:.27});
 box(-.12,.44,1.68,.80,.75,.43,PAL.oak,MAT.wood,{round:.055});pot(.32,4.24,.78);lum('hall',-.55,1.94,2.56,.91);
 for(let n=0;n<6;n++){box(-.61,1.22+n*.078,-4.84,.24,.035,.11,n%2?PAL.oak:PAL.ivory,MAT.wood);}
 // Kinetic ceiling-fan blades and smart roller blinds (driven by live cover/fan states).
 cyl(-.55,1.99,2.43,.13,.09,PAL.bronze,MAT.metal,{metal:.8});
 for(let j=0;j<4;j++){const a=j*Math.PI/2;box(-.55+Math.cos(a)*.37,1.96,2.43+Math.sin(a)*.37,.67,.048,.21,PAL.cream,MAT.fan,{rot:-a,round:.045});}
 for(let j=0;j<10;j++){box(2.27,1.57-j*.116,-4.83,1.57,.055,.055,PAL.ivory,MAT.blind,{round:.013});}
 // Wall art built as actual painted panels (not perspective-corrected screenshots).
 for(const a of [[-5.78,1.35,-5.048,.89,.64,PAL.rust], [4.59,1.35,-5.048,1.10,.69,PAL.blue]]){
  const [x,y,z,w,h,c]=a;box(x,y,z,w+.075,h+.075,.055,PAL.walnut,MAT.wood,{round:.02});box(x,y,z+.041,w,h,.017,PAL.ivory,MAT.plain);orb(x-.13,y,z+.055,.23,.19,.014,c,MAT.plain);orb(x+.19,y-.07,z+.057,.19,.15,.014,PAL.clay,MAT.plain);
 }
 // Emissive architectural strip along the plinth and cabinet lighting.
 box(0,-.245,5.268,14.21,.022,.025,PAL.gold,MAT.glow,{em:.49});box(0,-.245,-5.268,14.21,.022,.025,PAL.gold,MAT.glow,{em:.49});
 // Transparent glass panes / low entrance balustrade.
 box(-3.72,.27,5.025,3.29,.53,.042,PAL.glass,MAT.glass,{glass:true});box(5.28,.24,5.025,3.05,.48,.042,PAL.glass,MAT.glass,{glass:true});
 // Room status beacons float in scene and respond to live HA entities.
 const materialRooms=rooms.map(r=>({room:r.id,light:0}));
 // VERTEX + PHYSICALLY INSPIRED FRAGMENT LIGHTING: contact shadows, sun shadow map,
 // spatial warm bulbs, procedural materials, highlight roughness and ACES tone mapping.
 const vert=`#version 300 es
 precision highp float;
 layout(location=0) in vec3 aPosition;
 layout(location=1) in vec3 aNormal;
 layout(location=2) in vec3 aColor;
 layout(location=3) in vec4 aMaterial;
 uniform mat4 uVP;uniform mat4 uLightVP;uniform float uBlind;uniform float uFanPhase;
 out vec3 vWorld;out vec3 vNormal;out vec3 vColor;out vec4 vMat;out vec4 vShadow;
 void main(){vec3 wp=aPosition;vec3 norm=aNormal;
 if(aMaterial.x>10.5&&aMaterial.x<11.5)wp.y=mix(wp.y,1.92+(wp.y-1.05)*.055,uBlind);
 if(aMaterial.x>12.5&&aMaterial.x<13.5){float c=cos(uFanPhase),s=sin(uFanPhase);vec2 q=wp.xz-vec2(-.55,2.43);wp.xz=vec2(q.x*c-q.y*s,q.x*s+q.y*c)+vec2(-.55,2.43);norm.xz=vec2(norm.x*c-norm.z*s,norm.x*s+norm.z*c);}
 vWorld=wp;vNormal=norm;vColor=aColor;vMat=aMaterial;vShadow=uLightVP*vec4(wp,1.);gl_Position=uVP*vec4(wp,1.);}
 `;
 const frag=`#version 300 es
 precision highp float;precision highp sampler2DShadow;
 in vec3 vWorld;in vec3 vNormal;in vec3 vColor;in vec4 vMat;in vec4 vShadow;
 uniform sampler2DShadow uShadow;
 uniform vec3 uEye;uniform vec3 uSunDir;uniform float uDay;uniform float uWarm;uniform float uExposure;uniform vec2 uResolution;
 uniform vec4 uLights[12]; // xyz position / actual Home Assistant normalized intensity
 uniform int uLightCount;uniform float uSceneTime;uniform float uTV;
 out vec4 Frag;
 float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453123);}
 float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
 float shade(){vec3 q=vShadow.xyz/vShadow.w*.5+.5;if(q.x<0.||q.x>1.||q.y<0.||q.y>1.||q.z>1.)return 1.;float sh=0.;float bias=max(.0012,.0030*(1.-max(dot(normalize(vNormal),normalize(uSunDir)),0.)));for(int i=-2;i<=2;i++)for(int j=-2;j<=2;j++){sh+=texture(uShadow,vec3(q.xy+vec2(float(i),float(j))/2048.,q.z-bias));}return sh/25.;}
 vec3 matColor(vec3 col,float type,vec3 p){
  if(type>0.5&&type<1.5){vec2 plank=p.xz*vec2(.52,3.3);float grain=sin(p.z*36.+sin(p.x*1.9)*.8)+.36*sin(p.z*102.);float knot=noise(p.xz*4.0)*.18;float seam=step(.965,fract(plank.y+floor(plank.x)*.29));float crossing=step(.992,fract(plank.x));float variation=(hash(floor(plank))-.5)*.13;col*=1.+grain*.037+knot*.21+variation;col*=1.-.19*max(seam,crossing);}
  if(type>1.5&&type<2.5){float vein=sin(p.x*6.+p.z*3.+noise(p.xz*4.)*7.+sin(p.x*15.)*.35);float lines=smoothstep(.84,.97,vein);col=mix(col,vec3(.48,.47,.45),lines*.30);col*=.96+.08*noise(p.xz*13.);}
  if(type>2.5&&type<3.5){float threads=sin(p.x*460.)*sin(p.z*410.);col*=.94+.06*threads+.07*noise(p.xz*55.);}
  if(type>3.5&&type<4.5){vec2 g=fract(p.xz*2.3);float grout=1.-step(.023,min(min(g.x,g.y),min(1.-g.x,1.-g.y)));col*=1.-.13*grout+.04*noise(p.xz*8.);}
  if(type>4.5&&type<5.5){col*=.9+.10*noise(p.xz*65.)+.05*hash(floor(p.xz*140.));}
  if(type>6.5&&type<7.5){col*=.82+.20*noise(p.xz*16.+p.yy*5.);}
  if(type>8.5&&type<9.5){col*=.96+.045*noise(p.xz*8.);}
  return col;
 }
 vec3 aces(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
 void main(){
  vec3 n=normalize(vNormal),view=normalize(uEye-vWorld),sun=normalize(uSunDir),h=normalize(view+sun);
  float rough=vMat.y,metal=vMat.z,emis=vMat.w,type=vMat.x;
  vec3 albedo=matColor(vColor,type,vWorld);
  float lam=max(dot(n,sun),0.);float shadow=shade();
  // Low-frequency hemispherical bounce fills walls facing away from the sun.
  float skylight=(n.y*.5+.5)*.23+.24;
  vec3 illumination=vec3(.35,.40,.47)*(.43+uDay*.20)+vec3(.87,.89,.93)*skylight*(.35+uDay*.35);
  illumination+=mix(vec3(1.,.67,.39),vec3(1.0,.91,.80),uDay)*lam*shadow*(.13+uDay*2.25);
  vec3 warm=vec3(1.0,.68,.36);
  for(int i=0;i<12;i++){if(i>=uLightCount)break;vec3 d=uLights[i].xyz-vWorld;float ds=dot(d,d);float brightness=uLights[i].w;float reach=1./(1.+ds*.56);float ldot=max(dot(n,normalize(d)),0.);illumination+=warm*brightness*reach*(.26+.93*ldot)*.85;}
  // Highly controlled Fresnel specular captures brass, chrome, lacquer and porcelain.
  float specPower=mix(130.,9.,rough*rough);float spec=pow(max(dot(n,h),0.),specPower)*(1.-rough*.55)*(1.+metal*3.0);spec*=shadow*(.2+uDay*1.2);
  float f=pow(1.-max(dot(n,view),0.),5.);vec3 specColor=mix(vec3(.68,.73,.77),albedo,metal);
  vec3 radiance=albedo*illumination*(1.-metal*.72)+specColor*(spec+f*.075)*(1.-rough*.5);
  if(type>5.5&&type<6.5){float act=.12;for(int j=0;j<12;j++){if(j>=uLightCount)break;float nearLight=1.-smoothstep(.18,.45,distance(vWorld,uLights[j].xyz));act=max(act,uLights[j].w*nearLight);}radiance+=albedo*emis*act*2.9;}
  if(type>11.5&&type<12.5)radiance+=albedo*(uTV*.85+.025);
  if(type>9.5){radiance=mix(radiance,vec3(.37,.55,.61),.3);radiance+=pow(max(dot(reflect(-view,n),sun),0.),16.)*.28;}
  // Grade the environment, gentle atmospheric falloff behind walls.
  float depth=length(uEye-vWorld);radiance=mix(radiance,vec3(.16,.19,.23),clamp((depth-38.)/45.,0.,.35));
  radiance*=uExposure;
  Frag=vec4(pow(aces(radiance),vec3(1./2.2)),(type>9.5&&type<10.5)?0.26:1.0);
 }
 `;
 const shadowVert=`#version 300 es
 layout(location=0) in vec3 aPosition;uniform mat4 uLightVP;
 void main(){gl_Position=uLightVP*vec4(aPosition,1.);}`;
 const shadowFrag=`#version 300 es
 precision highp float;void main(){} `;
 const postVert=`#version 300 es
 precision highp float;const vec2 p[6]=vec2[](vec2(-1,-1),vec2(1,-1),vec2(-1,1),vec2(-1,1),vec2(1,-1),vec2(1,1));out vec2 uv;void main(){gl_Position=vec4(p[gl_VertexID],0,1);uv=p[gl_VertexID]*.5+.5;}`;
 const postFrag=`#version 300 es
 precision highp float;in vec2 uv;out vec4 frag;uniform sampler2D uScene;uniform vec2 uResolution;uniform float uBloom;uniform float uGrain;uniform float uFrame;
 float lum(vec3 c){return dot(c,vec3(.2126,.7152,.0722));}
 void main(){vec3 color=texture(uScene,uv).rgb;vec3 bloom=vec3(0);vec2 px=1./uResolution;for(int i=0;i<12;i++){float a=float(i)*6.2831853/12.;vec2 off=vec2(cos(a),sin(a));vec3 s=texture(uScene,uv+off*px*5.5).rgb;float k=smoothstep(.55,.97,lum(s));bloom+=s*k/12.;}color+=bloom*uBloom*.47;float vignette=1.-smoothstep(.21,.81,length((uv-.5)*vec2(1.25,1.05)));color*=.88+.12*vignette;float grain=(fract(sin(dot(uv*uResolution+uFrame,vec2(12.9898,78.233)))*43758.54)-.5)*uGrain;color+=grain;frag=vec4(color,1.);}`;
 function shader(t,src){let sh=gl.createShader(t);gl.shaderSource(sh,src);gl.compileShader(sh);if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS))throw new Error('Shader compilation: '+gl.getShaderInfoLog(sh));return sh;}
 function program(v,f){let p=gl.createProgram();gl.attachShader(p,shader(gl.VERTEX_SHADER,v));gl.attachShader(p,shader(gl.FRAGMENT_SHADER,f));gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw new Error('Shader link: '+gl.getProgramInfoLog(p));return p;}
 const paint=program(vert,frag),depthProgram=program(shadowVert,shadowFrag),post=program(postVert,postFrag);
 function bufferG(g){const vao=gl.createVertexArray();gl.bindVertexArray(vao);const vb=gl.createBuffer(),ib=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vb);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(g.p),gl.STATIC_DRAW);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint32Array(g.i),gl.STATIC_DRAW);
  for(let k=0;k<4;k++){const width=k===3?4:3;gl.enableVertexAttribArray(k);gl.vertexAttribPointer(k,width,gl.FLOAT,false,STRIDE*4,(k===0?0:k===1?3:k===2?6:9)*4);}gl.bindVertexArray(null);return {vao,num:g.i.length,vb,ib};}
 const meshes={solid:bufferG(solid),em:bufferG(emissive),glass:bufferG(transparent)};
 const shadowMap=gl.createTexture(),shadowFbo=gl.createFramebuffer();let shadowSize=2048;
 function makeShadow(){gl.bindTexture(gl.TEXTURE_2D,shadowMap);gl.texImage2D(gl.TEXTURE_2D,0,gl.DEPTH_COMPONENT24,shadowSize,shadowSize,0,gl.DEPTH_COMPONENT,gl.UNSIGNED_INT,null);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_COMPARE_MODE,gl.COMPARE_REF_TO_TEXTURE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_COMPARE_FUNC,gl.LEQUAL);gl.bindFramebuffer(gl.FRAMEBUFFER,shadowFbo);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.TEXTURE_2D,shadowMap,0);gl.drawBuffers([gl.NONE]);gl.readBuffer(gl.NONE);if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw new Error('Shadow framebuffer incomplete.');gl.bindFramebuffer(gl.FRAMEBUFFER,null);}
 makeShadow();
 let frameBuffer=null,frameTexture=null,frameDepth=null,W=0,H=0,ratio=1,quality=true,cinema=true;
 function makeTarget(){if(frameTexture)gl.deleteTexture(frameTexture);if(frameDepth)gl.deleteRenderbuffer(frameDepth);if(frameBuffer)gl.deleteFramebuffer(frameBuffer);frameBuffer=gl.createFramebuffer();frameTexture=gl.createTexture();frameDepth=gl.createRenderbuffer();gl.bindTexture(gl.TEXTURE_2D,frameTexture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,W,H,0,gl.RGBA,gl.UNSIGNED_BYTE,null);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.bindRenderbuffer(gl.RENDERBUFFER,frameDepth);gl.renderbufferStorage(gl.RENDERBUFFER,gl.DEPTH_COMPONENT24,W,H);gl.bindFramebuffer(gl.FRAMEBUFFER,frameBuffer);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,frameTexture,0);gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,frameDepth);gl.drawBuffers([gl.COLOR_ATTACHMENT0]);if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw new Error('Color framebuffer incomplete.');gl.bindFramebuffer(gl.FRAMEBUFFER,null);}
 function resize(){const r=host.getBoundingClientRect();const dpr=Math.min(devicePixelRatio||1,quality?1.65:1);const nw=Math.max(2,Math.floor(r.width*dpr)),nh=Math.max(2,Math.floor(r.height*dpr));if(nw===W&&nh===H)return;W=nw;H=nh;ratio=r.width/r.height;canvas.width=W;canvas.height=H;canvas.style.width='100%';canvas.style.height='100%';makeTarget();}
 const overlay=document.createElement('div');overlay.className='haven-room-overlay';shell.append(overlay);
 const labels=new Map();for(let r of rooms){const b=document.createElement('button');b.className='haven-room-chip';b.textContent=r.name;b.title='Explore '+r.full;b.onclick=()=>selectRoom(r.id,false);overlay.append(b);labels.set(r.id,b);}
 // Camera rig: orbit, drag-to-pan around target, cinematic transition, touch and wheel zoom.
 let yaw=.71,elev=.61,dist=31.8,tYaw=yaw,tElev=elev,tDist=dist;
 let target=[0,.36,0],desired=[0,.36,0],auto=false,top=false,moving=false,press=null,autoRaf=0;
 function eyePosition(){const c=Math.cos(elev);return [target[0]+Math.sin(yaw)*c*dist,target[1]+Math.sin(elev)*dist,target[2]+Math.cos(yaw)*c*dist];}
 let dayTime=17,dayCycle=false,lastFrame=performance.now(),lastLVP=null,lastVP=null,frame=0,blindOpen=0,fanAngle=0; const prefersReduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 const pointLights=new Float32Array(48);
 function sync(){let k=0;for(let b of bulbs){const list=devices.filter(d=>d.room===b.room&&d.domain==='light');const active=list.filter(d=>d.on),intensity=active.length?active.reduce((t,d)=>t+(d.brightness||80)/100,0)/active.length:0;pointLights[k*4]=b.x;pointLights[k*4+1]=b.y;pointLights[k*4+2]=b.z;pointLights[k*4+3]=intensity*b.power;k++;}}
 function select(id,animated=true){let r=rooms.find(x=>x.id===id);if(r){desired=[r.x*.46,.36,r.z*.46];tDist=25.6;tYaw=.71;tElev=.70;}else{desired=[0,.36,0];tDist=31.8;tYaw=.71;tElev=.61;}if(!animated){target=[...desired];dist=tDist;yaw=tYaw;elev=tElev;}labels.forEach((el,key)=>el.classList.toggle('chosen',key===id));}
 const down=e=>{press={x:e.clientX,y:e.clientY,prevX:e.clientX,prevY:e.clientY,t:performance.now(),drag:false};canvas.setPointerCapture(e.pointerId);};
 const move=e=>{if(!press)return;let dx=e.clientX-press.prevX,dy=e.clientY-press.prevY;press.prevX=e.clientX;press.prevY=e.clientY;if(Math.hypot(e.clientX-press.x,e.clientY-press.y)>5)press.drag=true;if(press.drag){tYaw+=dx*.007;tElev=Math.min(1.45,Math.max(.25,tElev+dy*.006));auto=false;$('#rotateView').classList.remove('active');}};
 const up=e=>{if(!press)return;let p=press;press=null;if(p.drag||performance.now()-p.t>520)return;let rect=canvas.getBoundingClientRect();let xy=[(e.clientX-rect.left)/rect.width,(e.clientY-rect.top)/rect.height];
 // Ray cast the real 3D floor footprint, not merely the nearest room caption.
 const eye=eyePosition(),forward=unit(sub(target,eye)),right=unit(cross(forward,[0,1,0])),up=cross(right,forward),fov=Math.tan(35*Math.PI/360);
 const nx=xy[0]*2-1,ny=1-xy[1]*2,ray=unit(add(forward,add(scale(right,nx*fov*rect.width/rect.height),scale(up,ny*fov))));
 let chosen=null;if(ray[1]<-.0001){const t=(.045-eye[1])/ray[1];if(t>0){const ground=add(eye,scale(ray,t));chosen=rooms.find(r=>Math.abs(ground[0]-r.x)<=r.w/2&&Math.abs(ground[2]-r.z)<=r.d/2)?.id||null;}}
 if(!chosen){let best=70;for(const r of rooms){const center=project([r.x,.35,r.z]);if(!center)continue;let d=Math.hypot((center[0]-xy[0])*rect.width,(center[1]-xy[1])*rect.height);if(d<best){best=d;chosen=r.id;}}}
 if(chosen)selectRoom(chosen,false);};
 canvas.addEventListener('pointerdown',down);canvas.addEventListener('pointermove',move);canvas.addEventListener('pointerup',up);canvas.addEventListener('pointercancel',()=>press=null);canvas.addEventListener('wheel',e=>{e.preventDefault();tDist=Math.max(17,Math.min(44,tDist+e.deltaY*.012))},{passive:false});
 let prevTouches=null;canvas.addEventListener('touchmove',e=>{if(e.touches.length!==2){prevTouches=null;return;}const a=e.touches[0],b=e.touches[1],d=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);if(prevTouches)tDist=Math.max(17,Math.min(44,tDist+(prevTouches-d)*.035));prevTouches=d;},{passive:true});canvas.addEventListener('touchend',()=>prevTouches=null);
 function project(pos){if(!lastVP)return null;const m=lastVP,[x,y,z]=pos;const p=[m[0]*x+m[4]*y+m[8]*z+m[12],m[1]*x+m[5]*y+m[9]*z+m[13],m[2]*x+m[6]*y+m[10]*z+m[14],m[3]*x+m[7]*y+m[11]*z+m[15]];if(p[3]<=0)return null;return [p[0]/p[3]*.5+.5,-p[1]/p[3]*.5+.5];}
 function updateLabels(){let rect=host.getBoundingClientRect();if(!rect.width||!rect.height)return;for(const r of rooms){const p=project([r.x,1.84,r.z]),el=labels.get(r.id);if(!p)continue;el.style.left=`${Math.round(p[0]*rect.width)}px`;el.style.top=`${Math.round(p[1]*rect.height)}px`;el.style.opacity=p[0]<-.04||p[0]>1.04||p[1]<-.1||p[1]>1.1?0:1;}}
 $('#resetView').onclick=()=>{top=false;selectRoom('all',true);$('#topView').classList.remove('active')};$('#resetCameraFooter').onclick=()=>{top=false;selectRoom('all',true);$('#topView').classList.remove('active')};
 $('#topView').onclick=()=>{top=!top;tElev=top?1.55:.61;tDist=top?27:31.8;desired=[0,.36,0];$('#topView').classList.toggle('active',top);};
 $('#rotateView').onclick=()=>{auto=!auto;$('#rotateView').classList.toggle('active',auto);};
 $('#qualityToggle').onclick=()=>{quality=!quality;$('#qualityToggle').classList.toggle('active',quality);shadowSize=quality?2048:1024;makeShadow();resize();};
 $('#cinemaToggle').onclick=()=>{cinema=!cinema;$('#cinemaToggle').classList.toggle('active',cinema);};
 $('#timeSlider').oninput=e=>{dayTime=+e.target.value;dayCycle=false;$('#animateDay').classList.remove('active');$('#animateDay').textContent='▶ DAY CYCLE';};
 $('#animateDay').onclick=()=>{dayCycle=!dayCycle;$('#animateDay').classList.toggle('active',dayCycle);$('#animateDay').textContent=dayCycle?'Ⅱ PAUSE CYCLE':'▶ DAY CYCLE';};
 function draw(){autoRaf=requestAnimationFrame(draw);const now=performance.now(),dt=Math.min(.05,Math.max(0,(now-lastFrame)/1000));lastFrame=now;frame++;
  resize();if(auto&&!prefersReduced)tYaw+=dt*.15;if(dayCycle){dayTime=(dayTime+dt*.32)%24;$('#timeSlider').value=dayTime;}
  const label=dayTime>=5&&dayTime<10?'Morning':dayTime>=10&&dayTime<16?'Daylight':dayTime>=16&&dayTime<20?'Golden hour':'Night';let hh=Math.floor(dayTime),mm=Math.floor((dayTime-hh)*60);$('#timeValue').textContent=label+' · '+String(hh).padStart(2,'0')+':'+String(mm).padStart(2,'0');
  yaw+=(tYaw-yaw)*Math.min(1,dt*7);elev+=(tElev-elev)*Math.min(1,dt*7);dist+=(tDist-dist)*Math.min(1,dt*7);for(let i=0;i<3;i++)target[i]+=(desired[i]-target[i])*Math.min(1,dt*4.8);
  const eye=eyePosition(),proj=perspective(35*Math.PI/180,W/H,.1,150),view=lookAt(eye,target),VP=mult(proj,view);lastVP=VP;
  let a=(dayTime-6)/24*Math.PI*2,day=Math.max(0,Math.sin(a)),sunDir=unit([-Math.cos(a)*.64,Math.max(.08,day),.52]);const skyColor=day<.2?[.030,.047,.076]:day<.6?[.07,.085,.11]:[.11,.125,.15],lw=.50+day*1.0;
  const sunEye=scale(sunDir,28),lightView=lookAt(sunEye,[0,0,0]),lightVP=mult(ortho(-18,18,-16,16,.5,72),lightView);lastLVP=lightVP;
  gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.disable(gl.CULL_FACE);
  // 2048 px directional cast shadows; transparent panels never cast opaque shadows.
  gl.bindFramebuffer(gl.FRAMEBUFFER,shadowFbo);gl.viewport(0,0,shadowSize,shadowSize);gl.clearDepth(1);gl.clear(gl.DEPTH_BUFFER_BIT);gl.colorMask(false,false,false,false);gl.useProgram(depthProgram);gl.uniformMatrix4fv(gl.getUniformLocation(depthProgram,'uLightVP'),false,lightVP);
  gl.bindVertexArray(meshes.solid.vao);gl.drawElements(gl.TRIANGLES,meshes.solid.num,gl.UNSIGNED_INT,0);
  gl.bindVertexArray(meshes.em.vao);gl.drawElements(gl.TRIANGLES,meshes.em.num,gl.UNSIGNED_INT,0);
  gl.colorMask(true,true,true,true);
  // Filmic shaded geometry, warm spatial light sources, shadows and procedural PBR.
  gl.bindFramebuffer(gl.FRAMEBUFFER,frameBuffer);gl.viewport(0,0,W,H);gl.clearColor(...skyColor,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(paint);
  const uniform=(name)=>gl.getUniformLocation(paint,name);
  gl.uniformMatrix4fv(uniform('uVP'),false,VP);gl.uniformMatrix4fv(uniform('uLightVP'),false,lightVP);gl.uniform3fv(uniform('uEye'),eye);gl.uniform3fv(uniform('uSunDir'),sunDir);gl.uniform1f(uniform('uDay'),day);gl.uniform1f(uniform('uWarm'),Math.max(0,1-Math.abs(dayTime-18)/3));gl.uniform1f(uniform('uExposure'),.6+day*.12);gl.uniform2f(uniform('uResolution'),W,H);gl.uniform1i(uniform('uLightCount'),Math.min(12,bulbs.length));gl.uniform4fv(uniform('uLights[0]'),pointLights);gl.uniform1f(uniform('uSceneTime'),now*.001);
  const opened=devices.some(d=>d.domain==='cover'&&d.room==='bedroom'&&d.on)?1:0;blindOpen+=(opened-blindOpen)*Math.min(1,dt*3.0);
  const fans=devices.filter(d=>d.domain==='fan'&&d.room==='hall');const spinning=fans.length?fans.some(f=>f.on):true;if(spinning)fanAngle+=dt*(fans.length?2.1:.43);
  gl.uniform1f(uniform('uBlind'),blindOpen);gl.uniform1f(uniform('uFanPhase'),fanAngle);
  const television=devices.some(d=>d.domain==='media_player'&&d.room==='living'&&d.on);
  gl.uniform1f(uniform('uTV'),television?1:0);
  gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,shadowMap);gl.uniform1i(uniform('uShadow'),0);
  gl.bindVertexArray(meshes.solid.vao);gl.drawElements(gl.TRIANGLES,meshes.solid.num,gl.UNSIGNED_INT,0);
  gl.bindVertexArray(meshes.em.vao);gl.drawElements(gl.TRIANGLES,meshes.em.num,gl.UNSIGNED_INT,0);
  gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.depthMask(false);gl.bindVertexArray(meshes.glass.vao);gl.drawElements(gl.TRIANGLES,meshes.glass.num,gl.UNSIGNED_INT,0);gl.depthMask(true);gl.disable(gl.BLEND);
  // Native post processing: bloom convolution, subtle film grain and vignetting.
  gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.viewport(0,0,W,H);gl.disable(gl.DEPTH_TEST);gl.useProgram(post);gl.activeTexture(gl.TEXTURE1);gl.bindTexture(gl.TEXTURE_2D,frameTexture);gl.uniform1i(gl.getUniformLocation(post,'uScene'),1);gl.uniform2f(gl.getUniformLocation(post,'uResolution'),W,H);gl.uniform1f(gl.getUniformLocation(post,'uBloom'),cinema?.72:0);gl.uniform1f(gl.getUniformLocation(post,'uGrain'),cinema?.005:0);gl.uniform1f(gl.getUniformLocation(post,'uFrame'),frame);gl.bindVertexArray(null);gl.drawArrays(gl.TRIANGLES,0,6);
  if(frame%4===0)updateLabels();
 }
 sync();select(selectedRoom,false);const observer=new ResizeObserver(resize);observer.observe(host);resize();draw();
 return {select,sync,dispose(){cancelAnimationFrame(autoRaf);observer.disconnect();canvas.remove();overlay.remove();gl.deleteTexture(shadowMap);gl.deleteFramebuffer(shadowFbo);}};
}
