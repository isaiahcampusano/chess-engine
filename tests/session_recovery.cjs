const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const baseURL = process.env.CHESS_TEST_URL || 'http://127.0.0.1:5055';
const missing = { error: 'Choose an opponent before starting the game.', code: 'opponent_selection_required', needs_selection: true };
const reply = { engine_move: 'e7e5', score: 0, nodes: 1, depth: 1, timed_out: false, game_over: false };
let browser;
before(async () => { browser = await chromium.launch({ headless: true }); });
after(async () => { await browser?.close(); });

async function setup(t, bot = 'martin', suffix = '') {
  const context = await browser.newContext();
  t.after(() => context.close());
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  t.after(() => assert.deepEqual(errors, []));
  await page.route('**/api/eval', route => route.fulfill({ json: { evaluation_cp: 0 } }));
  await page.goto(baseURL + suffix);
  await page.locator('#opponentDialog[open]').waitFor();
  await page.locator(`[data-bot="${bot}"]`).click();
  await page.locator('#opponentDialog').waitFor({ state: 'hidden' });
  return { context, page };
}

async function playE4(page) {
  await page.locator('#myBoard .square-e2').click();
  await page.locator('#myBoard .square-e4').click();
}

async function waitRecovery(page) {
  await page.locator('#reconnectButton').waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.querySelector('#reconnectButton').disabled);
  assert.equal(await page.locator('#retryButton').isVisible(), false);
}

async function loseSession(t, bot) {
  const state = await setup(t, bot);
  const requests = [];
  await state.page.route('**/move', async route => {
    requests.push(route.request().postDataJSON());
    if (requests.length === 1) await route.continue();
    else await route.fulfill({ json: reply });
  });
  await state.context.clearCookies();
  await playE4(state.page);
  await waitRecovery(state.page);
  return { ...state, requests };
}

for (const bot of ['rookie', 'hustler', 'professor', 'martin']) {
  test(`lost session reconnects ${bot} without resetting position`, async t => {
    const { page, requests } = await loseSession(t, bot);
    const history = await page.locator('#moveHistory').innerText();
    assert.match(history, /e4/);
    await page.locator('#reconnectButton').click();
    await page.waitForFunction(() => document.querySelector('#moveHistory').textContent.includes('e5'));
    assert.equal(requests.length, 2);
    assert.equal(requests[1].fen, requests[0].fen);
    assert.match(await page.locator('#moveHistory').innerText(), /e4[\s\S]*e5/);
    assert.equal(await page.locator('#reconnectButton').isVisible(), false);
  });
}

test('network failure preserves history and permits a second reconnect', async t => {
  const { page, requests } = await loseSession(t);
  const history = await page.locator('#moveHistory').innerText();
  await page.route('**/select_bot', route => route.abort('failed'));
  await page.locator('#reconnectButton').click();
  await page.locator('#errorBox').waitFor({ state: 'visible' });
  assert.equal(await page.locator('#moveHistory').innerText(), history);
  assert.equal(requests.length, 1);
  await page.unroute('**/select_bot');
  await page.locator('#reconnectButton').click();
  await page.waitForFunction(() => document.querySelector('#moveHistory').textContent.includes('e5'));
});

test('repeated session loss stops instead of looping', async t => {
  const { page, requests } = await loseSession(t);
  let retries = 0;
  await page.route('**/move', async route => {
    retries++;
    await route.fulfill({ status: 409, json: missing });
  });
  await page.locator('#reconnectButton').click();
  await waitRecovery(page);
  assert.equal(retries, 1);
  assert.equal(requests.length, 1);
  assert.match(await page.locator('#moveHistory').innerText(), /e4/);
});

test('same server opponent resumes without posting another selection', async t => {
  const { page, context, requests } = await loseSession(t);
  await context.request.post(baseURL + '/select_bot', { data: { bot_id: 'martin' } });
  let posts = 0;
  page.on('request', req => { if (req.url().endsWith('/select_bot') && req.method() === 'POST') posts++; });
  await page.locator('#reconnectButton').click();
  await page.waitForFunction(() => document.querySelector('#moveHistory').textContent.includes('e5'));
  assert.equal(posts, 0);
  assert.equal(requests.length, 2);
});

test('conflicting opponent remains locked and board stays intact', async t => {
  const { page, context, requests } = await loseSession(t);
  await context.request.post(baseURL + '/select_bot', { data: { bot_id: 'rookie' } });
  await page.locator('#reconnectButton').click();
  await page.waitForFunction(() => document.querySelector('#errorBox').textContent.includes('different opponent'));
  assert.equal(requests.length, 1);
  assert.match(await page.locator('#moveHistory').innerText(), /e4/);
  assert.equal((await (await context.request.get(baseURL + '/select_bot')).json()).selected, 'rookie');
});

test('removed opponent explains that a new game is required', async t => {
  const { page, requests } = await loseSession(t);
  await page.route('**/select_bot', route => route.request().method() === 'POST'
    ? route.fulfill({ status: 400, json: { error: 'Invalid bot ID.' } })
    : route.continue());
  await page.locator('#reconnectButton').click();
  await page.waitForFunction(() => document.querySelector('#errorBox').textContent.includes('no longer available'));
  assert.equal(requests.length, 1);
  assert.match(await page.locator('#moveHistory').innerText(), /e4/);
});

test('duplicate reconnect clicks issue one selection request', async t => {
  const { page, requests } = await loseSession(t);
  let checks = 0;
  await page.route('**/select_bot', async route => {
    checks++;
    await route.continue();
  });
  await page.locator('#reconnectButton').evaluate(button => { button.click(); button.click(); });
  await page.waitForFunction(() => document.querySelector('#moveHistory').textContent.includes('e5'));
  assert.equal(checks, 2); // One GET, one POST.
  assert.equal(requests.length, 2);
});

test('new game invalidates an outstanding reconnect response', async t => {
  const { page, requests } = await loseSession(t);
  let release;
  let arrived;
  const received = new Promise(resolve => { arrived = resolve; });
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/select_bot', async route => {
    arrived();
    await gate;
    await route.fulfill({ json: { selected: 'martin', needs_selection: false } }).catch(() => {});
  });
  await page.locator('#reconnectButton').click();
  await received;
  await page.locator('#newGameButton').click();
  await page.locator('#opponentDialog[open]').waitFor();
  release();
  assert.equal(await page.locator('#reconnectButton').isVisible(), false);
  assert.doesNotMatch(await page.locator('#moveHistory').innerText(), /e4/);
  assert.equal(requests.length, 1);
});

test('ordinary move retry and new game still work', async t => {
  const { page } = await setup(t);
  let moves = 0;
  await page.route('**/move', route => ++moves === 1
    ? route.fulfill({ status: 500, json: { error: 'Temporary engine failure' } })
    : route.fulfill({ json: reply }));
  await playE4(page);
  await page.locator('#retryButton').waitFor({ state: 'visible' });
  assert.equal(await page.locator('#reconnectButton').isVisible(), false);
  await page.locator('#retryButton').click();
  await page.waitForFunction(() => document.querySelector('#moveHistory').textContent.includes('e5'));
  await page.locator('#newGameButton').click();
  await page.locator('#opponentDialog[open]').waitFor();
  assert.doesNotMatch(await page.locator('#moveHistory').innerText(), /e4/);
});

test('late selection-required move response cannot interrupt a new game', async t => {
  const { page } = await setup(t);
  await page.route('**/move', route => route.fulfill({ status: 409, json: missing }));
  const response = page.waitForResponse(res => res.url().endsWith('/move'));
  await playE4(page);
  await response;
  // The response is received, but the old request is still in its minimum thinking delay.
  await page.locator('#newGameButton').click();
  await page.locator('#opponentDialog[open]').waitFor();
  await page.locator('[data-bot="rookie"]').click();
  await page.locator('#opponentDialog').waitFor({ state: 'hidden' });
  await page.waitForTimeout(1700);
  assert.equal(await page.locator('#reconnectButton').isVisible(), false);
  assert.equal(await page.locator('#errorBox').isVisible(), false);
  assert.match(await page.locator('#opponentName').innerText(), /Rookie/);
  assert.doesNotMatch(await page.locator('#moveHistory').innerText(), /e4/);
});

test('completed game remains reviewable and allows a new opponent', async t => {
  const { page } = await setup(t, 'martin', '/?test=analysis');
  const ended = page.waitForResponse(res => res.url().endsWith('/end_game'));
  await page.locator('#myBoard .square-f7').click();
  await page.locator('#myBoard .square-g7').click();
  assert.equal((await ended).status(), 200);
  await page.locator('#reviewGameButton').waitFor({ state: 'visible' });
  assert.equal(await page.locator('#reconnectButton').isVisible(), false);
  assert.match(await page.locator('#moveHistory').innerText(), /Qg7#/);
  await page.locator('#newGameButton').click();
  await page.locator('#opponentDialog[open]').waitFor();
  await page.locator('[data-bot="rookie"]').click();
  await page.locator('#opponentDialog').waitFor({ state: 'hidden' });
  assert.match(await page.locator('#opponentName').innerText(), /Rookie/);
});
