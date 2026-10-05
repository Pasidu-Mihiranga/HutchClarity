/** Same key ThemeProvider writes. The boot script reads it before the first paint. */
export const THEME_STORAGE_KEY = "clarity.theme";

/**
 * Runs while the document is parsed, before the system dark colours can paint.
 * Light or dark is an override. System leaves the attribute off so the media query applies.
 */
export const themeBootScript = `(function(){try{var t=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});var d=document.documentElement;if(t==="light"||t==="dark")d.setAttribute("data-theme",t);else d.removeAttribute("data-theme");}catch(e){}})();`;
