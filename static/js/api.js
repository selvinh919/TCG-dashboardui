export async function fetchInventory() {
  const res = await fetch('/api/inventory');
  return res.json();
}
