import {expect,it} from "vitest";
import QRCode from "qrcode";
import decode from "jsqr";
it("decodes the same 48-character QR payload issued by My tickets",()=>{
 const credential="0123456789abcdef".repeat(3);
 const qr=QRCode.create(credential,{errorCorrectionLevel:"M"});
 const scale=6,margin=4,size=(qr.modules.size+margin*2)*scale;
 const pixels=new Uint8ClampedArray(size*size*4);
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  const row=Math.floor(y/scale)-margin,col=Math.floor(x/scale)-margin;
  const dark=row>=0&&col>=0&&row<qr.modules.size&&col<qr.modules.size&&qr.modules.get(row,col);
  const offset=(y*size+x)*4;
  pixels[offset]=pixels[offset+1]=pixels[offset+2]=dark?0:255;pixels[offset+3]=255;
 }
 expect(decode(pixels,size,size,{inversionAttempts:"dontInvert"})?.data).toBe(credential);
});
