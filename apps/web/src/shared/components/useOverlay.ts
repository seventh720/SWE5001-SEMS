import {useLayoutEffect, type RefObject} from "react";

// Native popovers enter the top layer, escaping card overflow and animated ancestors.
// Keep the element in its React/DOM parent so nested selectors and outside-click work.
export function useOverlay(open: boolean, panel: RefObject<HTMLElement | null>, anchor: RefObject<HTMLElement | null>, maxWidth = Infinity, maxHeight = 230) {
  useLayoutEffect(() => {
    const element = panel.current;
    const target = anchor.current;
    if (!open || !element || !target || !element.showPopover) return;
    element.setAttribute("popover", "manual");
    element.showPopover();
    function position() {
      const rect = target!.getBoundingClientRect();
      const viewport = window.visualViewport;
      const left = viewport?.offsetLeft ?? 0;
      const top = viewport?.offsetTop ?? 0;
      const width = viewport?.width ?? window.innerWidth;
      const height = viewport?.height ?? window.innerHeight;
      const panelWidth = Math.min(rect.width, maxWidth, width - 24);
      Object.assign(element!.style, {
        position: "fixed", inset: "auto", margin: "0",
        width: `${panelWidth}px`, maxHeight: `${Math.min(maxHeight, height - 24)}px`,
        left: `${Math.max(left + 12, Math.min(rect.left, left + width - panelWidth - 12))}px`,
      });
      const panelHeight = element!.getBoundingClientRect().height;
      const below = rect.bottom + 6;
      const above = rect.top - panelHeight - 6;
      element!.style.top = `${Math.max(top + 12, Math.min(below + panelHeight > top + height - 12 && above >= top + 12 ? above : below, top + height - panelHeight - 12))}px`;
    }
    position();
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    window.visualViewport?.addEventListener("resize", position);
    window.visualViewport?.addEventListener("scroll", position);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(position);
    observer?.observe(element);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
      window.visualViewport?.removeEventListener("resize", position);
      window.visualViewport?.removeEventListener("scroll", position);
      if (element.matches(":popover-open")) element.hidePopover();
    };
  }, [open, panel, anchor, maxWidth, maxHeight]);
}
