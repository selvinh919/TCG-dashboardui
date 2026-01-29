import { fetchInventory } from './api.js';

async function loadStats() {
  const data = await fetchInventory();
  const stats = document.getElementById('stats');

  stats.innerHTML = `
    <div class="bg-white p-5 rounded-xl">Ask<br>$${data.totals.ask}</div>
    <div class="bg-white p-5 rounded-xl">Market<br>$${data.totals.market}</div>
    <div class="bg-white p-5 rounded-xl">Delta<br>$${data.totals.delta}</div>
  `;
}

loadStats();
