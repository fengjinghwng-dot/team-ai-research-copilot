/** All team dates use Beijing time, including clients located in another time zone. */
export function teamDate(value = new Date()): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(value);
}
