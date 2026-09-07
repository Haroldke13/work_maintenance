/* Live help desk behaviour: Socket.IO notifications and the self-help picker. */
const HelpDesk = (() => {
    const TONES = { info: 'primary', success: 'success', warning: 'warning', danger: 'danger' };

    function toast(title, body, tone = 'info') {
        const stack = document.getElementById('toastStack');
        if (!stack) return;

        const el = document.createElement('div');
        el.className = `toast align-items-center border-0 mb-2 show shadow`;
        el.innerHTML = `
            <div class="toast-header">
                <span class="badge text-bg-${TONES[tone] || 'primary'} me-2">&nbsp;</span>
                <strong class="me-auto">${title}</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">${body}</div>`;
        stack.prepend(el);

        el.querySelector('.btn-close').addEventListener('click', () => el.remove());
        setTimeout(() => el.remove(), 12000);
    }

    function setLive(dotId, labelId, on, text) {
        const dot = dotId && document.getElementById(dotId);
        const label = labelId && document.getElementById(labelId);
        if (dot) dot.classList.toggle('on', on);
        if (label) label.textContent = text;
    }

    function watchDashboard({ liveDotId, liveLabelId }) {
        const socket = io();

        socket.on('connect', () => {
            socket.emit('join_dashboard', {}, (reply) => {
                if (reply && reply.joined) {
                    setLive(liveDotId, liveLabelId, true, 'Live — new tickets appear instantly');
                    applyStats(reply.stats);
                } else {
                    setLive(liveDotId, liveLabelId, false, 'Not receiving live updates');
                }
            });
        });

        socket.on('disconnect', () => setLive(liveDotId, liveLabelId, false, 'Reconnecting…'));

        socket.on('ticket:created', (ticket) => {
            toast(`New complaint · ${ticket.reference}`,
                  `${ticket.subject}<br><span class="text-secondary">${ticket.reporter_name} · ${ticket.department} · ${ticket.priority_label}</span>`,
                  ticket.priority === 'urgent' ? 'danger' : 'info');
            markStale();
        });

        socket.on('ticket:resolved', (data) => {
            const who = data.self_resolved
                ? `${data.ticket.reporter_name} reported it fixed`
                : `resolved by ${data.resolved_by}`;
            toast(`Resolved · ${data.reference}`, `${data.subject}<br><span class="text-secondary">${who}</span>`, 'success');
            markStale();
        });

        socket.on('ticket:updated', (data) => markStale());
        socket.on('ticket:comment', (data) => {
            if (data.event.actor_role === 'reporter') {
                toast(`Reply · ${data.ticket.reference}`, `${data.event.actor_name}: ${data.event.message}`, 'info');
            }
        });
        socket.on('stats', applyStats);
    }

    function applyStats(stats) {
        if (!stats) return;
        Object.entries(stats).forEach(([key, value]) => {
            document.querySelectorAll(`[data-stat="${key}"]`).forEach((el) => { el.textContent = value; });
        });
    }

    let staleShown = false;
    function markStale() {
        if (staleShown) return;
        staleShown = true;
        const banner = document.createElement('div');
        banner.className = 'alert alert-info d-flex justify-content-between align-items-center';
        banner.innerHTML = `<span>The queue has changed.</span>
            <button class="btn btn-sm btn-primary" onclick="location.reload()">Refresh</button>`;
        document.querySelector('main').prepend(banner);
    }

    function watchTicket({ reference, token, liveDotId }) {
        const socket = io();

        socket.on('connect', () => {
            socket.emit('join_ticket', { reference, token }, (reply) => {
                setLive(liveDotId, null, !!(reply && reply.joined));
            });
        });
        socket.on('disconnect', () => setLive(liveDotId, null, false));

        socket.on('ticket:comment', (data) => {
            if (data.ticket.reference !== reference) return;
            appendEvent(data.event);
            toast('New message', `${data.event.actor_name}: ${data.event.message}`, 'info');
        });

        socket.on('ticket:updated', (data) => {
            if (data.ticket.reference !== reference) return;
            appendEvent(data.event);
            toast('Ticket updated', `Status is now ${data.ticket.status_label}.`, 'success');
        });
    }

    function appendEvent(event) {
        const timeline = document.getElementById('timeline');
        if (!timeline || !event) return;

        const li = document.createElement('li');
        li.className = `actor-${event.actor_role}`;
        const status = event.event_type === 'status'
            ? `<div class="fw-semibold">Status: ${event.from_status} &rarr; ${event.to_status}</div>` : '';
        li.innerHTML = `
            <div class="d-flex justify-content-between gap-2 small text-secondary">
                <span><strong class="text-body">${event.actor_name}</strong> · ${event.actor_role}</span>
                <span>${event.created_at}</span>
            </div>${status}
            <div class="body">${event.message || ''}</div>`;
        timeline.appendChild(li);
    }

    function wireCategoryPicker({ selectId, otherWrapperId, otherInputId, listId, emptyId, noteId, steps }) {
        const select = document.getElementById(selectId);
        const wrapper = document.getElementById(otherWrapperId);
        const otherInput = document.getElementById(otherInputId);
        const list = document.getElementById(listId);
        const empty = document.getElementById(emptyId);
        const note = document.getElementById(noteId);
        if (!select) return;

        const render = () => {
            const key = select.value;
            const isOther = key === 'other';
            wrapper.classList.toggle('d-none', !isOther);
            otherInput.required = isOther;

            const items = steps[key] || [];
            list.innerHTML = items.map((step) => `<li class="mb-2">${step}</li>`).join('');
            list.classList.toggle('d-none', items.length === 0);
            empty.classList.toggle('d-none', items.length > 0);
            note.classList.toggle('d-none', items.length === 0 || isOther);
        };

        select.addEventListener('change', render);
        render();
    }

    return { watchDashboard, watchTicket, wireCategoryPicker, toast };
})();
