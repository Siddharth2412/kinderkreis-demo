export function validatePasswords(password, confirm) {
  if (password.length < 8) return "Das Passwort muss mindestens 8 Zeichen lang sein.";
  if (password !== confirm) return "Die Passwörter stimmen nicht überein.";
  return null;
}
