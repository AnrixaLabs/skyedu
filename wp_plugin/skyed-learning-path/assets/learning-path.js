/* SkyEd Learning Path. Runs entirely in memory; no network or storage. */
(function (root) {
  'use strict';

  const COPY = {
    en: {
      title: 'Your four-week learning plan', subtitle: 'A home activity outline—not a language-level assessment.',
      rhythm: 'Suggested rhythm', rhythmValue: '4 sessions per week', session: 'minutes per session',
      starting: 'Starting point', emphasis: 'Learning focus', weekly: 'Four-week outline',
      guidance: 'For parents', guidanceText: 'Follow the child’s interest, repeat familiar activities and stop when attention drops. Adjust the suggested time as needed.',
      weeks: ['1 · Listen and notice', '2 · Repeat and respond', '3 · Use language in play', '4 · Review and share'],
      steps: {
        listening: ['Listen to 4–6 useful words with clear picture cues.', 'Play “point to the picture” and follow simple directions.', 'Use the target language during a short game or routine.', 'Mix familiar words into a new listening game.'],
        speaking: ['Model 3–5 everyday expressions without demanding repetition.', 'Ask simple either/or questions and allow thinking time.', 'Practice short exchanges through pretend play.', 'Use familiar expressions in a new situation.'],
        reading: ['Explore one illustrated story and describe the pictures.', 'Replay the story and invite predictions.', 'Retell with pictures, objects or gestures.', 'Revisit the story and notice repeated words or phrases.']
      },
      ages: {
        a34: 'Use gestures, toys and picture prompts. Adult-led play is more important than worksheets.',
        a56: 'Add short question-and-answer exchanges and simple story sequencing.',
        a79: 'Invite short independent responses, story summaries and age-appropriate text.'
      },
      levels: {
        new: 'Begin with familiar objects and one short expression at a time.',
        words: 'Combine familiar words into useful two- or three-word phrases.',
        sentences: 'Build flexible sentences and encourage natural responses.'
      },
      ageLabels: { a34: 'Ages 3–4', a56: 'Ages 5–6', a79: 'Ages 7–9' },
      goalLabels: { listening: 'Listening', speaking: 'Speaking', reading: 'Reading' },
      print: 'Print plan', newPlan: 'Change choices'
    },
    zh: {
      title: '专属四周英语学习计划', subtitle: '这是一份家庭练习建议，不是英语水平测评结果。',
      rhythm: '建议安排', rhythmValue: '每周练习4次', session: '每次练习分钟数',
      starting: '孩子的学习起点', emphasis: '本次学习重点', weekly: '四周学习安排',
      guidance: '给家长的建议', guidanceText: '根据孩子的兴趣灵活调整，多重复已经熟悉的活动。如果孩子注意力下降，可以提前结束，不必强求完成时长。',
      weeks: ['第1周 · 听一听、认一认', '第2周 · 跟着说、做回应', '第3周 · 在游戏中使用英语', '第4周 · 复习与表达'],
      steps: {
        listening: ['借助图片听辨4—6个常用单词。', '玩“指一指”游戏，听懂并完成简单指令。', '把目标词汇融入一个简短的日常小游戏。', '在新的听力游戏中复习熟悉的词汇。'],
        speaking: ['自然示范3—5个生活中常用的表达，不强迫跟读。', '用简单的二选一问题引导孩子开口，并留出思考时间。', '通过角色扮演练习简短对话。', '换一个生活场景，使用已经熟悉的表达。'],
        reading: ['一起看一本图画故事书，描述画面内容。', '再次听故事，鼓励孩子猜测接下来会发生什么。', '借助图片、玩具或动作复述故事。', '重读故事，发现重复出现的单词和句子。']
      },
      ages: {
        a34: '多用动作、玩具和图片。这个年龄更适合亲子游戏，不需要大量纸笔练习。',
        a56: '逐渐加入简短问答，以及按顺序描述故事画面的活动。',
        a79: '鼓励孩子独立作答、简短复述，并接触符合年龄的阅读文本。'
      },
      levels: {
        new: '从熟悉的物品开始，每次练习一个简短表达。',
        words: '把熟悉的单词组合成有实际意义的两到三个词的短语。',
        sentences: '练习灵活运用简单句，鼓励孩子自然回应。'
      },
      ageLabels: { a34: '3—4岁', a56: '5—6岁', a79: '7—9岁' },
      goalLabels: { listening: '听力理解', speaking: '口语表达', reading: '阅读与故事' },
      print: '打印计划', newPlan: '重新选择'
    }
  };

  const ALLOWED = {
    age: ['a34', 'a56', 'a79'],
    level: ['new', 'words', 'sentences'],
    goal: ['listening', 'speaking', 'reading'],
    minutes: ['10', '15', '20']
  };

  function buildPlan(values, language) {
    const lang = language === 'zh' ? 'zh' : 'en';
    for (const [key, allowed] of Object.entries(ALLOWED)) {
      if (!allowed.includes(String(values[key] || ''))) {
        throw new TypeError('Invalid learning-path selection: ' + key);
      }
    }
    const t = COPY[lang];
    return {
      language: lang,
      title: t.title,
      subtitle: t.subtitle,
      overview: [
        [t.rhythm, t.rhythmValue],
        [t.session, String(values.minutes)],
        [t.starting, t.ageLabels[values.age]],
        [t.emphasis, t.goalLabels[values.goal]]
      ],
      heading: t.weekly,
      weeks: t.weeks.map((title, i) => ({ title, activity: t.steps[values.goal][i] })),
      guidanceTitle: t.guidance,
      guidance: [t.ages[values.age], t.levels[values.level], t.guidanceText],
      print: t.print,
      change: t.newPlan
    };
  }

  function element(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function render(target, plan, form) {
    target.replaceChildren();
    const header = element('div', 'skyed-path__result-header');
    header.append(element('h3', '', plan.title), element('p', '', plan.subtitle));
    target.append(header);

    const overview = element('dl', 'skyed-path__overview');
    plan.overview.forEach(([label, value]) => {
      const cell = element('div', 'skyed-path__metric');
      cell.append(element('dt', '', label), element('dd', '', value));
      overview.append(cell);
    });
    target.append(overview, element('h4', '', plan.heading));

    const steps = element('ol', 'skyed-path__weeks');
    plan.weeks.forEach((week) => {
      const li = element('li', 'skyed-path__week');
      li.append(element('strong', '', week.title), element('p', '', week.activity));
      steps.append(li);
    });
    target.append(steps, element('h4', '', plan.guidanceTitle));

    const tips = element('ul', 'skyed-path__tips');
    plan.guidance.forEach((tip) => tips.append(element('li', '', tip)));
    target.append(tips);
    const actions = element('div', 'skyed-path__actions');
    const change = element('button', 'skyed-path__secondary', plan.change);
    change.type = 'button';
    change.addEventListener('click', () => {
      target.hidden = true;
      form.hidden = false;
      form.querySelector('select').focus();
    });
    const print = element('button', 'skyed-path__submit', plan.print);
    print.type = 'button';
    print.addEventListener('click', () => window.print());
    actions.append(change, print);
    target.append(actions);
    form.hidden = true;
    target.hidden = false;
    target.focus();
  }

  function init() {
    document.querySelectorAll('[data-skyed-learning-path]').forEach((rootElement) => {
      const form = rootElement.querySelector('form');
      const result = rootElement.querySelector('.skyed-path__result');
      if (!form || !result) return;
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const values = Object.fromEntries(new FormData(form).entries());
        try {
          render(result, buildPlan(values, rootElement.dataset.lang), form);
        } catch (error) {
          // Invalid or tampered selections remain private to the browser.
          form.reportValidity();
        }
      });
    });
  }

  root.SkyEdLearningPath = Object.freeze({ buildPlan });
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})(typeof window !== 'undefined' ? window : globalThis);
