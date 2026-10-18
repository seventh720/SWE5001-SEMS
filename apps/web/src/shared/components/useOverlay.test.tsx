// @vitest-environment jsdom
import {useRef} from 'react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {act,cleanup,render,screen} from '@testing-library/react';
import {useOverlay} from './useOverlay';
function Fixture({open=true}:{open?:boolean}){const anchor=useRef<HTMLButtonElement>(null),panel=useRef<HTMLDivElement>(null);useOverlay(open,panel,anchor,380);return <><button ref={anchor}>Anchor</button>{open&&<div ref={panel} data-testid="panel">Options</div>}</>}
let shown=vi.fn<() => void>(),hidden=vi.fn<() => void>(),disconnect=vi.fn<() => void>();
beforeEach(()=>{
 shown=vi.fn();hidden=vi.fn();disconnect=vi.fn();
 vi.stubGlobal('innerWidth',390);vi.stubGlobal('innerHeight',600);
 vi.stubGlobal('visualViewport',undefined);
 vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){disconnect()}});
 Object.defineProperty(HTMLElement.prototype,'showPopover',{configurable:true,value:shown});
 Object.defineProperty(HTMLElement.prototype,'hidePopover',{configurable:true,value:hidden});
 vi.spyOn(HTMLElement.prototype,'matches').mockImplementation(selector=>selector===':popover-open');
 vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockImplementation(function(this:HTMLElement){return this.tagName==='BUTTON'?{left:300,top:500,bottom:550,width:200,height:50} as DOMRect:{height:180} as DOMRect});
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();delete (HTMLElement.prototype as Partial<HTMLElement>).showPopover;delete (HTMLElement.prototype as Partial<HTMLElement>).hidePopover});
it('flips above a low trigger and keeps a right-edge panel within the viewport',()=>{
 const view=render(<Fixture/>);const panel=screen.getByTestId('panel');
 expect(shown).toHaveBeenCalledTimes(1);expect(panel.style.left).toBe('178px');expect(panel.style.top).toBe('314px');
 expect(panel.style.width).toBe('200px');expect(panel.style.maxHeight).toBe('230px');
 view.unmount();expect(hidden).toHaveBeenCalledTimes(1);expect(disconnect).toHaveBeenCalledTimes(1);
});
it('repositions and bounds height when a phone viewport shrinks',()=>{
 render(<Fixture/>);vi.stubGlobal('innerHeight',220);act(()=>window.dispatchEvent(new Event('resize')));
 const panel=screen.getByTestId('panel');expect(panel.style.top).toBe('28px');expect(panel.style.maxHeight).toBe('196px');
});
it('leaves the CSS overlay available on browsers without native popovers',()=>{
 delete (HTMLElement.prototype as Partial<HTMLElement>).showPopover;
 render(<Fixture/>);expect(screen.getByTestId('panel').hasAttribute('popover')).toBe(false);expect(shown).not.toHaveBeenCalled();
});
