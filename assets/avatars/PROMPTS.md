# Reviewer 2 아바타 프롬프트

- 생성 도구: Codex CLI imagegen (`codex-image` 플러그인의 `generate`)
- 참조 이미지: 저장소 루트의 `logo.png` (캐릭터와 그림체)
- 실행 형식: 아래 공통 프롬프트 뒤에 시트별 9칸 목록과 저장 경로를 붙여 시트마다 한 번씩 실행한다.
- 후처리: `slice_avatars.py`가 흰 구분선을 감지해 9칸으로 자르고 384×384로 저장한다. 감정 태그는 `manifest.json`, 원형 미리보기는 `preview.png`.

## 공통 프롬프트

```text
Image 1 is the CHARACTER and STYLE reference: "Reviewer 2", a grumpy senior academic peer reviewer drawn as a flat two-color vector line-art logo. Copy his identity exactly: an older man with a high balding forehead, a few combed-back strands of hair on top and short tufts above the ears, thin round wire glasses, heavy expressive eyebrows, a long face, a white shirt collar showing under a dark crew-neck sweater with a big bold varsity-style red number "2" in the middle of the chest. Copy the art style exactly: flat vector illustration, clean bold white outlines of uniform thickness on a solid deep navy background (#0E2445), the figure filled with the same navy, white (#F8F9F4) for line work and highlights, and signal red (#C8232A) as the only accent color (the "2", props, small emotion marks). No gradients, no shading, no texture, no 3D, no photorealism.

Create ONE square (1:1) image: an expression sheet made of NINE separate avatar illustrations of the SAME character, arranged in a perfectly even grid of 3 rows and 3 columns. All nine tiles are exactly the same size and perfectly square, separated by thin straight pure-white gutters of equal width, with the same thin white margin around the outside of the sheet. Inside each tile the background is solid flat navy edge to edge: do NOT draw the white inner frame border from the reference, no border or frame inside the tiles.

Identical in every tile: avatar framing showing his head and upper chest, face centered and large, the whole head inside the tile with a little navy space above it, the top of the red "2" visible on his chest; the same glasses, hair, collar, sweater, line weight, and palette. He must be unmistakably the same character in all nine tiles.

Different in each tile: ONLY the facial expression, the head angle, a hand gesture, and the small prop named for that tile. Keep hands and props close to his face and upper chest, never in the tile corners, because each tile will also be shown as a small circle cut from its center. Make each expression big, exaggerated, and readable at thumbnail size, like a sticker pack. Any visible hand is drawn in the same white line style with exactly four fingers and one thumb. Small emotion marks (sweat drop, anger vein, question mark, exclamation mark, lightbulb, "Z" letters, motion lines, sparkles) are allowed in white or red when a tile calls for them. No words, labels, numbers, captions, or watermark anywhere, except the red "2" on the sweater and any stamp text a tile explicitly asks for.

The nine tiles, in reading order (left to right, top row first):
```

## 시트 A (기본 감정) → sheets/sheet-a-basic.png

```text
1. The default: a stern frown, brows drawn together, mouth a flat downturned line, arms crossed high on his chest exactly like the reference, staring straight at the viewer.
2. Skeptical: glasses slid down to the tip of his nose, eyes peering over the rims at the viewer, one eyebrow raised very high, lips pressed tight.
3. Grudging approval: a small reluctant closed-lip smile, eyebrows relaxed, mid-nod with tiny motion lines above his head.
4. Laughing hard: head thrown back, mouth wide open, eyes squeezed shut, a tear at the corner of one eye, one hand on his chest.
5. Surprised: eyebrows shot up high, eyes wide behind the glasses, mouth a small round "o", glasses lifted slightly off his nose, a red exclamation mark beside his head.
6. Angry: brows slammed down into a deep V, teeth clenched, a red anger-vein mark on his forehead, small white steam puffs from his ears.
7. Disappointed: eyes closed, a long downturned mouth, slow head shake shown by small motion lines, a little white sigh puff in front of his mouth.
8. Thinking: eyes looking up and to the side, thumb and index finger stroking his chin, lips pursed, three small white dots above his head.
9. Tired: a huge yawn with one hand covering his mouth, eyes shut, glasses tilted crooked.
```

## 시트 B (심사) → sheets/sheet-b-review.png

```text
1. Reading closely: holding a few manuscript pages up beside his face, eyes narrowed scanning them; the pages show only abstract grey-white lines, no readable text.
2. Red pen: gripping a red pen upright beside his cheek like a weapon, a wicked satisfied grin, one eyebrow raised.
3. The verdict: holding the red rubber stamp from the reference up beside his face with its round face turned toward the viewer, the stamp face reading "MAJOR REVISIONS" in white letters exactly like the reference, a fierce triumphant grin.
4. Rare acceptance: holding up a small red round rubber stamp beside his face whose face reads "ACCEPT" in white letters, eyes averted, a pained reluctant grimace, one sweat drop on his temple.
5. Citation check: holding a magnifying glass in front of one eye so that eye looks huge, the other eye squinting, suspicious pursed mouth.
6. Accusing: index finger pointing straight at the viewer beside his face, stern glare, mouth open mid-sentence.
7. Facepalm: one palm pressed against his forehead pushing his glasses askew, mouth a tight grimace.
8. Unconvinced: both palms turned up beside his shoulders in a shrug, eyebrows raised, flat mouth, head tilted.
9. Thumbs down: one thumb down held beside his face, eyes half-lidded, a disgusted frown.
```

## 시트 C (연구 상황) → sheets/sheet-c-research.png

```text
1. Waiting: wrist raised beside his face looking at his wristwatch, impatient flat mouth, one eyebrow cocked, small motion lines from a tapping finger.
2. Idea: index finger pointing straight up beside his face, eyes wide and bright, open-mouth smile, a red lightbulb above his head.
3. Celebrating: both fists raised beside his face, a huge open-mouth grin, eyes shut with joy, small white sparkles around him.
4. Confused: head tilted, one eyebrow up and the other down, a crooked wavy mouth, a red question mark beside his head.
5. Thumbs up: one thumb up held beside his face, a confident small smile, one eye winking.
6. Coffee break: holding a steaming mug just under his chin with both hands, eyes half-closed and calm, a contented little smile.
7. Exhausted: glasses crooked on his nose, eyes drooping and unfocused, mouth slack, a few hair strands sticking up, two sweat drops.
8. Oops: a sheepish awkward grin showing clenched teeth, one hand scratching the back of his head, eyes looking away, one sweat drop.
9. Hello: one open hand raised beside his face waving, a warm friendly smile, eyes kind.
```

## 시트 D (강한 감정) → sheets/sheet-d-strong.png

```text
1. Shocked: both hands pressed against his cheeks, eyes huge, mouth open in a scream, glasses jumping off his nose, red exclamation marks.
2. Suspicious: eyes narrowed into a sideways squint, mouth twisted to one side, chin lowered.
3. Eye roll: eyes rolled all the way up, a bored smirk, head tilted back slightly.
4. Tsk tsk: index finger raised and wagging beside his face with motion lines, eyes closed, lips pursed.
5. Heartbroken: big tears streaming from behind his glasses, eyebrows drawn up in the middle, lower lip trembling.
6. Smug: chin lifted high, eyes closed, a wide satisfied closed-lip grin, arms crossed high on his chest.
7. Relieved: eyes gently closed, a soft exhaling smile, one hand flat on his chest, a small white sigh puff.
8. Delighted: sparkling wide eyes with star highlights, a huge delighted smile, both hands clasped together under his chin.
9. Goodnight: dozing with his head drooping to one side, eyes closed, a small red nightcap on his head, glasses pushed up onto his forehead, white "Z" letters floating up.
```

## 끝맺음 (모든 시트 공통)

```text
If the image generation is rejected by the safety system, do not retry with reworded prompts; report the failure and stop. Save the result to <repo>/assets/avatars/sheets/<sheet file> and do not overwrite any existing file.
```
