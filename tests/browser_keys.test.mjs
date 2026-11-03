import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../browser_keys.py', import.meta.url), 'utf8');
const js = source.match(/JS = r"""([\s\S]*?)"""/)[1];
const storage = new Map();
const events = [];
const context = {
  window: {location: {pathname: '/runway'}},
  localStorage: {
    setItem: (key, value) => storage.set(key, value),
    getItem: key => storage.get(key) ?? null,
    removeItem: key => storage.delete(key),
  },
};
const render = vm.runInNewContext('(' + js.replace('export default function', 'function') + ')', context);
const run = data => render({data, setStateValue: (_, event) => events.push(event)});
run({restore: false});
assert.equal(storage.size, 0);
assert.equal(events.length, 0);
run({command: {id: 's1', action: 'save', keys: {api_key: '  user-test  ', unknown: 'excluded'}}});
assert.equal(storage.size, 1);
assert.equal(events.at(-1).action, 'saved');
assert.ok(![...storage.values()][0].includes('excluded'));
run({restore: true});
assert.equal(events.at(-1).keys.api_key, 'user-test');
context.window.location.pathname = '/other-app';
run({restore: true});
assert.equal(Object.keys(events.at(-1).keys).length, 0);
context.window.location.pathname = '/runway';
run({command: {id: 'd1', action: 'delete'}});
assert.equal(storage.size, 0);
run({restore: true});
assert.equal(Object.keys(events.at(-1).keys).length, 0);
context.localStorage.setItem = () => {throw Error('private-browser-details');};
run({command: {id: 'blocked', action: 'save', keys: {api_key: 'user-test'}}});
assert.equal(events.at(-1).action, 'unavailable');
assert.ok(!JSON.stringify(events.at(-1)).includes('private-browser-details'));
console.log('Browser key storage: opt-in, restore, path isolation, delete, blocked storage passed.');
