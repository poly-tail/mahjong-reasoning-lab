export function isTextEditing(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.matches('input,textarea,select') ||
      target.isContentEditable === true)
  );
}
export function composing(
  event: { isComposing?: boolean; keyCode?: number },
  active: boolean,
): boolean {
  return active || event.isComposing === true || event.keyCode === 229;
}
