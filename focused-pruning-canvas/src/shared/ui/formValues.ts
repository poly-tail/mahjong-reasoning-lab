export const formText = (form: FormData, name: string) =>
  String(form.get(name) ?? '');
export const formNumber = (form: FormData, name: string) =>
  Number(formText(form, name));
