const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../wp_plugin/skyed-learning-path/assets/learning-path.js'), 'utf8');
const context = { window: {} }; // no document: test pure planner without network
vm.runInNewContext(source, context);
const { buildPlan } = context.window.SkyEdLearningPath;

for (const lang of ['en', 'zh']) {
  for (const age of ['a34', 'a56', 'a79']) {
    for (const goal of ['listening', 'speaking', 'reading']) {
      test(`${lang}/${age}/${goal}: four complete, localized weeks`, () => {
        const result = buildPlan({ age, goal, level: 'words', minutes: '15' }, lang);
        assert.equal(result.language, lang);
        assert.equal(result.weeks.length, 4);
        assert.equal(result.guidance.length, 3);
        assert.ok(result.weeks.every(w => w.title.length > 5 && w.activity.length > 8));
        assert.ok(result.overview.every(row => row[0] && row[1]));
        assert.match(result.subtitle, lang === 'zh' ? /测评/ : /assessment/);
      });
    }
  }
}

test('rejects manipulated selections rather than trusting input', () => {
  assert.throws(() => buildPlan({ age: 'evil', goal: 'reading', level: 'new', minutes: '10' }, 'en'), /Invalid learning-path selection/);
  assert.throws(() => buildPlan({ age: 'a34', goal: 'reading', level: 'new', minutes: '100' }, 'zh'), /Invalid learning-path selection/);
});
