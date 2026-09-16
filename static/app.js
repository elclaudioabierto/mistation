const audio = document.getElementById('audio');
const button = document.getElementById('listen');
const buttonText = document.getElementById('listenText');
const status = document.getElementById('status');
const listenerCount = document.getElementById('listenerCount');
const navAir = document.getElementById('navAir');
const record = document.querySelector('.hero-record .record');

async function updateStats() {
  try {
    const data = await (await fetch('/api/status', {cache: 'no-store'})).json();
    const active = data.source !== 'offline';
    listenerCount.textContent = data.listeners;
    navAir.textContent = active ? 'ON AIR' : 'OFF AIR';
    navAir.classList.toggle('offline', !active);
    status.textContent = active ? 'STREAM STANDING BY' : 'BROADCAST OFFLINE';
  } catch {
    listenerCount.textContent = '—';
    navAir.textContent = 'OFF AIR';
    navAir.classList.add('offline');
    status.textContent = 'STREAM NOT REACHABLE';
  }
}

updateStats();
setInterval(updateStats, 5000);

button.addEventListener('click', async () => {
  if (audio.paused) {
    try {
      await audio.play();
      buttonText.textContent = 'PAUSE BROADCAST';
      status.textContent = 'YOU ARE ON THE AIR';
    } catch {
      status.textContent = 'STREAM NOT REACHABLE YET';
    }
  } else {
    audio.pause();
    buttonText.textContent = 'LISTEN LIVE';
    status.textContent = 'STREAM STANDING BY';
  }
});

audio.addEventListener('play', () => record.classList.add('spinning'));
audio.addEventListener('pause', () => record.classList.remove('spinning'));
