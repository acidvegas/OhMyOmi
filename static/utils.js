// static - Developed by acidvegas in JavaScript (https://github.com/acidvegas)
// utils.js

const wires = document.querySelector('.wires');

function highlight(name) {
	wires.classList.toggle('dim', !!name);
	document.querySelectorAll('[data-wire]').forEach(el => el.classList.toggle('on', el.dataset.wire === name));
}

document.querySelectorAll('[data-wire]').forEach(el => {
	el.addEventListener('mouseenter', () => highlight(el.dataset.wire));
	el.addEventListener('mouseleave', () => highlight(null));
});
