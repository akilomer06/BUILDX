export function parseMinor(value: string): number {
  if (!/^(0|[1-9]\d{0,6})(\.\d{1,2})?$/.test(value)) throw new Error('Enter an amount with at most two decimal places.')
  const [whole, fraction = ''] = value.split('.')
  const minor = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))
  if (minor <= 0n || minor > 100000000n) throw new Error('Amount must be positive and within the sandbox limit of INR 10,00,000.')
  return Number(minor)
}
export const money = (minor: number, currency = 'INR') => new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(minor / 100)
