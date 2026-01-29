import { fetchInventory } from './api.js';

async function loadInventory() {
  const data = await fetchInventory();
  const table = document.getElementById('table');

  table.innerHTML = `
    <table class="w-full">
      ${data.items.map(i => `
        <tr>
          <td>${i.name}</td>
          <td>${i.qty}</td>
          <td>$${i.price}</td>
          <td>$${i.market}</td>
        </tr>
      `).join('')}
    </table>
  `;
}

loadInventory();
