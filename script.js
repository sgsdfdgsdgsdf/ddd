const scenes = document.querySelectorAll('.scene');
const playBtn = document.getElementById('playBtn');
const progressBar = document.getElementById('progressBar');
const timerEl = document.getElementById('timer');

const SCENE_DURATIONS = [3500, 4500, 4500, 4500, 4000, 5000];
const TOTAL = SCENE_DURATIONS.reduce((a, b) => a + b, 0);

let timers = [];
let startTime = 0;
let progressFrame = null;

function clearAll() {
  timers.forEach(t => clearTimeout(t));
  timers = [];
  if (progressFrame) cancelAnimationFrame(progressFrame);
  scenes.forEach(s => s.classList.remove('active'));
}

function updateProgress() {
  const elapsed = performance.now() - startTime;
  const pct = Math.min(100, (elapsed / TOTAL) * 100);
  progressBar.style.width = pct + '%';
  timerEl.textContent =
    (elapsed / 1000).toFixed(1) + 's / ' + (TOTAL / 1000).toFixed(1) + 's';
  if (elapsed < TOTAL) {
    progressFrame = requestAnimationFrame(updateProgress);
  } else {
    timerEl.textContent = (TOTAL / 1000).toFixed(1) + 's / ' + (TOTAL / 1000).toFixed(1) + 's';
  }
}

function play() {
  clearAll();
  startTime = performance.now();
  progressFrame = requestAnimationFrame(updateProgress);

  let cumulative = 0;
  scenes.forEach((scene, i) => {
    timers.push(setTimeout(() => {
      scenes.forEach(s => s.classList.remove('active'));
      scene.classList.add('active');
    }, cumulative));
    cumulative += SCENE_DURATIONS[i];
  });

  // Mantém a última cena ativa ao final
  timers.push(setTimeout(() => {
    progressBar.style.width = '100%';
  }, TOTAL));
}

playBtn.addEventListener('click', play);

// Auto-play ao carregar
window.addEventListener('load', () => {
  setTimeout(play, 300);
});
