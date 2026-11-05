import { expect, test } from 'vitest'
import { money, parseMinor } from './money'
test('INR uses rupees, paise and Indian digit grouping',()=>{
  expect(money(12345)).toBe('₹123.45')
  expect(money(12345678)).toBe('₹1,23,456.78')
  expect(money(-1)).toBe('-₹0.01')
})
test('decimal entry maps exactly to integer minor units',()=>{expect(parseMinor('0.01')).toBe(1);expect(parseMinor('123.45')).toBe(12345);expect(parseMinor('1000000')).toBe(100000000)})
test.each(['0','-1','1.001','1e3','1,000','NaN','Infinity','1000000.01'])('rejects unsafe money input %s',value=>expect(()=>parseMinor(value)).toThrow())
