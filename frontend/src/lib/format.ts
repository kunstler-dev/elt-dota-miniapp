export const fmt = (n: number) => Math.floor(n).toLocaleString('ru-RU')

export function short(n: number): string {
  if (n >= 1e9) return (n / 1e9).toFixed(2).replace('.', ',') + 'B'
  if (n >= 1e6) return (n / 1e6).toFixed(2).replace('.', ',') + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(1).replace('.', ',') + 'K'
  return String(Math.floor(n))
}
