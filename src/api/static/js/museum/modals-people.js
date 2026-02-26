'use strict';

Modals.AddInterviewee = (() => {
        function init() {
            // Event listeners are already set up in initEventListeners()
        }

        function open() {
            Modals._openModal(DOM.addIntervieweeModal);
            DOM.newIntervieweeName.focus();
        }

        function close() {
            Modals._closeModal(DOM.addIntervieweeModal);
            DOM.newIntervieweeName.value = '';
        }

        return { init, open, close };
})();


Modals.Contacts = (() => {
        const DEFAULT_PAGE_SIZE = 25;
        const MIN_PAGE_SIZE = 5;
        const MAX_PAGE_SIZE = 500;
        let pageSize = DEFAULT_PAGE_SIZE;
        let currentPage = 0;
        let totalContacts = 0;
        const selectedIds = new Set();
        let sortColumn = 'name';
        let sortOrder = 'asc';

        function getPageSizeFromInputs() {
            const topVal = DOM.contactsPageSize ? parseInt(DOM.contactsPageSize.value, 10) : NaN;
            const bottomVal = DOM.contactsPageSizeBottom ? parseInt(DOM.contactsPageSizeBottom.value, 10) : NaN;
            const val = !isNaN(topVal) ? topVal : (!isNaN(bottomVal) ? bottomVal : DEFAULT_PAGE_SIZE);
            return Math.min(MAX_PAGE_SIZE, Math.max(MIN_PAGE_SIZE, val));
        }

        function syncPageSizeInputs() {
            if (DOM.contactsPageSize) DOM.contactsPageSize.value = pageSize;
            if (DOM.contactsPageSizeBottom) DOM.contactsPageSizeBottom.value = pageSize;
        }

        function updatePaginationUI(offset, totalPages) {
            const start = totalContacts === 0 ? 0 : offset + 1;
            const end = Math.min(offset + pageSize, totalContacts);
            const info = `Showing ${start}-${end} of ${totalContacts}`;
            if (DOM.contactsPaginationInfoTop) DOM.contactsPaginationInfoTop.textContent = info;
            if (DOM.contactsPaginationInfoBottom) DOM.contactsPaginationInfoBottom.textContent = info;
            const prevBtns = [DOM.contactsPrevBtn, DOM.contactsPrevBtnTop];
            const nextBtns = [DOM.contactsNextBtn, DOM.contactsNextBtnTop];
            prevBtns.forEach(b => { if (b) b.disabled = currentPage <= 0; });
            nextBtns.forEach(b => { if (b) b.disabled = currentPage >= totalPages - 1; });
        }

        function updateDeleteSelectedUI() {
            const count = selectedIds.size;
            if (DOM.contactsDeleteSelectedBtn) {
                DOM.contactsDeleteSelectedBtn.style.display = count > 0 ? '' : 'none';
            }
            if (DOM.contactsSelectedCount) {
                DOM.contactsSelectedCount.textContent = count;
            }
        }

        function updateSortIndicators() {
            document.querySelectorAll('.contacts-sortable-header').forEach(th => {
                const col = th.dataset.sort;
                th.classList.remove('contacts-sort-asc', 'contacts-sort-desc');
                if (col === sortColumn) {
                    th.classList.add(sortOrder === 'asc' ? 'contacts-sort-asc' : 'contacts-sort-desc');
                }
            });
        }

        function onSortHeaderClick(e) {
            const th = e.target.closest('.contacts-sortable-header');
            if (!th) return;
            const col = th.dataset.sort;
            if (!col) return;
            if (sortColumn === col) {
                sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn = col;
                sortOrder = 'desc';
            }
            loadContacts(0);
        }

        async function loadContacts(page = 0) {
            if (!DOM.contactsLoading || !DOM.contactsTableContainer || !DOM.contactsTableBody) return;
            pageSize = getPageSizeFromInputs();
            syncPageSizeInputs();
            DOM.contactsLoading.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading contacts...';
            DOM.contactsLoading.style.display = 'block';
            DOM.contactsTableContainer.style.display = 'none';
            try {
                const offset = page * pageSize;
                const hasMessagesOnly = DOM.contactsHasMessagesOnly && DOM.contactsHasMessagesOnly.checked;
                const emailContainsAt = DOM.contactsEmailContainsAt && DOM.contactsEmailContainsAt.checked;
                const excludePhoneNumbers = DOM.contactsExcludePhoneNumbers && DOM.contactsExcludePhoneNumbers.checked;
                const searchTerm = DOM.contactsSearch ? DOM.contactsSearch.value.trim() : '';
                const url = new URL('/contacts', window.location.origin);
                url.searchParams.set('limit', String(pageSize));
                url.searchParams.set('offset', String(offset));
                url.searchParams.set('order_by', sortColumn);
                url.searchParams.set('order', sortOrder);
                if (hasMessagesOnly) url.searchParams.set('has_messages', 'true');
                if (emailContainsAt) url.searchParams.set('email_contains_at', 'true');
                if (excludePhoneNumbers) url.searchParams.set('exclude_phone_numbers', 'true');
                if (searchTerm) url.searchParams.set('search', searchTerm);
                const response = await fetch(url.toString());
                if (!response.ok) throw new Error('Failed to load contacts');
                const data = await response.json();
                const contacts = data.contacts || [];
                totalContacts = data.total || 0;
                currentPage = page;

                DOM.contactsTableBody.innerHTML = '';
                contacts.forEach(c => {

                    const row = document.createElement('tr');
                    row.style.borderBottom = '1px solid #eee';
                    row.dataset.contactId = c.id;
                    const canSelect = c.id !== 0;
                    const cb = canSelect ? `<input type="checkbox" class="contacts-row-cb" data-contact-id="${c.id}">` : '';
                    const deleteBtn = canSelect ? `<button type="button" class="contacts-delete-btn modal-btn modal-btn-secondary" data-contact-id="${c.id}" title="Delete contact" style="padding: 4px 8px; font-size: 0.85em;"><i class="fas fa-trash-alt"></i></button>` : '';
                    const contactName = c.name || '';
                    row.innerHTML = `
                        <td style="padding: 8px; text-align: center;">${cb}</td>
                        <td style="padding: 8px;width: 300px;">${escapeHtml(contactName)}</td>
                        <td style="padding: 8px;">${escapeHtml(c.email || '-')}</td>
                        <td style="padding: 8px; text-align: center;width: 100px;">${renderEmailCountCell(c.numemail, contactName)}</td>
                        <td style="padding: 8px; text-align: center;width: 100px;">${renderCountCell(c.numsms, contactName)}</td>
                        <td style="padding: 8px; text-align: center;width: 100px;">${renderCountCell(c.numwhatsapp, contactName)}</td>
                        <td style="padding: 8px; text-align: center;width: 100px;">${renderCountCell(c.numimessages, contactName)}</td>
                        <td style="padding: 8px; text-align: center;width: 100px;">${renderCountCell(c.numinstagram, contactName)}</td>
                        <td style="padding: 8px; text-align: center;width: 100px;">${renderCountCell(c.numfacebook, contactName)}</td>
                        <td style="padding: 8px; text-align: center;width: 80px;">${deleteBtn}</td>
                    `;
                    DOM.contactsTableBody.appendChild(row);
                });

                DOM.contactsTableBody.querySelectorAll('.contacts-row-cb').forEach(el => {
                    el.addEventListener('change', (e) => {
                        const id = parseInt(e.target.dataset.contactId, 10);
                        if (e.target.checked) selectedIds.add(id);
                        else selectedIds.delete(id);
                        updateDeleteSelectedUI();
                    });
                    if (selectedIds.has(parseInt(el.dataset.contactId, 10))) el.checked = true;
                });

                DOM.contactsTableBody.querySelectorAll('.contacts-delete-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => handleDeleteSingle(e));
                });

                if (DOM.contactsSelectAll) {
                    DOM.contactsSelectAll.checked = false;
                    DOM.contactsSelectAll.indeterminate = false;
                }

                const totalPages = Math.ceil(totalContacts / pageSize) || 1;
                updatePaginationUI(offset, totalPages);
                updateDeleteSelectedUI();
                updateSortIndicators();

                DOM.contactsLoading.style.display = 'none';
                DOM.contactsTableContainer.style.display = 'block';
            } catch (err) {
                console.error('Error loading contacts:', err);
                DOM.contactsLoading.innerHTML = `<span style="color: #c00;">Error: ${err.message}</span>`;
                DOM.contactsLoading.style.display = 'block';
                DOM.contactsTableContainer.style.display = 'none';
            }
        }

        async function handleDeleteSingle(e) {
            const btn = e.target.closest('.contacts-delete-btn');
            if (!btn) return;
            const id = parseInt(btn.dataset.contactId, 10);
            if (isNaN(id) || id === 0) return;
            try {
                const response = await fetch(`/contacts/${id}`, { method: 'DELETE' });
                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }
                selectedIds.delete(id);
                const totalPages = Math.ceil((totalContacts - 1) / pageSize) || 1;
                const pageToLoad = currentPage >= totalPages && currentPage > 0 ? currentPage - 1 : currentPage;
                await loadContacts(pageToLoad);
            } catch (err) {
                console.error('Error deleting contact:', err);
                alert(`Error: ${err.message}`);
            }
        }

        async function handleDeleteSelected() {
            const ids = Array.from(selectedIds);
            if (ids.length === 0) return;
            if (ids.length > 1 && !confirm(`Delete ${ids.length} contacts? This cannot be undone.`)) return;
            try {
                const response = await fetch('/contacts/bulk-delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ids })
                });
                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }
                ids.forEach(id => selectedIds.delete(id));
                const totalPages = Math.ceil((totalContacts - ids.length) / pageSize) || 1;
                const pageToLoad = currentPage >= totalPages && currentPage > 0 ? currentPage - 1 : currentPage;
                await loadContacts(pageToLoad);
            } catch (err) {
                console.error('Error deleting contacts:', err);
                alert(`Error: ${err.message}`);
            }
        }
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function renderCountCell(value, contactName) {
            const isClickable = typeof value === 'number' && value > 0;
            const display = (typeof value === 'number' && value > 0) ? String(value) : '';
            if (isClickable) {
                return `<span class="contacts-count-link" data-contact-name="${escapeHtml(contactName || '')}" title="View messages">${display}</span>`;
            }
            return escapeHtml(display);
        }

        function renderEmailCountCell(value, contactName) {
            const isClickable = typeof value === 'number' && value > 0;
            const display = (typeof value === 'number' && value > 0) ? String(value) : '';
            if (isClickable) {
                return `<span class="contacts-email-count-link" data-contact-name="${escapeHtml(contactName || '')}" title="View emails">${display}</span>`;
            }
            return escapeHtml(display);
        }

        function onCountCellClick(e) {
            const link = e.target.closest('.contacts-count-link');
            if (link) {
                const contactName = link.dataset.contactName;
                if (contactName && Modals.SMSMessages && Modals.SMSMessages.openWithFilter) {
                    Modals.Contacts.close();
                    Modals.SMSMessages.openWithFilter(contactName);
                }
                return;
            }
            const emailLink = e.target.closest('.contacts-email-count-link');
            if (emailLink) {
                const contactName = emailLink.dataset.contactName;
                if (contactName && Modals.EmailGallery && Modals.EmailGallery.openContact) {
                    Modals.Contacts.close();
                    Modals.EmailGallery.openContact(contactName);
                }
            }
        }
        function open() {
            selectedIds.clear();
            Modals._openModal(DOM.contactsModal);
            loadContacts(0);
        }
        function close() {
            Modals._closeModal(DOM.contactsModal);
        }
        async function extractContacts() {
            if (!DOM.extractContactsBtn) return;
            const btn = DOM.extractContactsBtn;
            const origHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Extracting...';
            try {
                const response = await fetch('/contacts/extract', { method: 'POST' });
                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }
                const data = await response.json();
                if (data.status === 'started') {
                    alert('Contacts extract started. Open Import Controls tab for progress.');
                }
            } catch (err) {
                console.error('Error extracting contacts:', err);
                alert(`Error: ${err.message}`);
            } finally {
                btn.disabled = false;
                btn.innerHTML = origHtml;
            }
        }
        function onPageSizeChange() {
            pageSize = getPageSizeFromInputs();
            syncPageSizeInputs();
            loadContacts(0);
        }

        function onSelectAllClick(e) {
            const checked = e.target.checked;
            if (!DOM.contactsTableBody) return;
            DOM.contactsTableBody.querySelectorAll('.contacts-row-cb').forEach(el => {
                el.checked = checked;
                const id = parseInt(el.dataset.contactId, 10);
                if (checked) selectedIds.add(id);
                else selectedIds.delete(id);
            });
            updateDeleteSelectedUI();
        }

        function init() {
            if (DOM.closeContactsModalBtn) DOM.closeContactsModalBtn.addEventListener('click', close);
            if (DOM.contactsModal) DOM.contactsModal.addEventListener('click', (e) => { if (e.target === DOM.contactsModal) close(); });
            if (DOM.extractContactsBtn) DOM.extractContactsBtn.addEventListener('click', extractContacts);
            if (DOM.contactsDeleteSelectedBtn) DOM.contactsDeleteSelectedBtn.addEventListener('click', handleDeleteSelected);
            if (DOM.contactsSelectAll) DOM.contactsSelectAll.addEventListener('click', onSelectAllClick);
            document.querySelectorAll('.contacts-sortable-header').forEach(th => {
                th.addEventListener('click', onSortHeaderClick);
            });
            [DOM.contactsPrevBtn, DOM.contactsPrevBtnTop].forEach(b => {
                if (b) b.addEventListener('click', () => loadContacts(Math.max(0, currentPage - 1)));
            });
            [DOM.contactsNextBtn, DOM.contactsNextBtnTop].forEach(b => {
                if (b) b.addEventListener('click', () => loadContacts(currentPage + 1));
            });
            if (DOM.contactsPageSize) DOM.contactsPageSize.addEventListener('change', onPageSizeChange);
            if (DOM.contactsPageSizeBottom) DOM.contactsPageSizeBottom.addEventListener('change', onPageSizeChange);
            if (DOM.contactsHasMessagesOnly) DOM.contactsHasMessagesOnly.addEventListener('change', () => loadContacts(0));
            if (DOM.contactsEmailContainsAt) DOM.contactsEmailContainsAt.addEventListener('change', () => loadContacts(0));
            if (DOM.contactsExcludePhoneNumbers) DOM.contactsExcludePhoneNumbers.addEventListener('change', () => loadContacts(0));
            if (DOM.contactsTableBody) DOM.contactsTableBody.addEventListener('click', onCountCellClick);
            if (DOM.contactsSearch) {
                const runSearch = () => loadContacts(0);
                DOM.contactsSearch.addEventListener('keydown', (e) => { if (e.key === 'Enter') runSearch(); });
                DOM.contactsSearch.addEventListener('blur', runSearch);
            }
        }
        return { init, open, close };
})();


Modals.Relationships = (() => {
        let cy = null;
        let hideTimeout = null;

        function getTypeFilterParams() {
            const types = ['friend', 'family', 'colleague', 'acquaintance', 'business', 'social', 'promotional', 'unknown'];
            const selected = types.filter(t => {
                const cb = document.getElementById('rel-type-' + t);
                return cb && cb.checked;
            });
            return selected.length > 0 ? selected.join(',') : null;
        }

        function getSourceFilterParams() {
            const sources = ['email', 'facebook', 'whatsapp', 'sms-imessage', 'instagram'];
            const selected = sources.filter(s => {
                const cb = document.getElementById('rel-source-' + s);
                return cb && cb.checked;
            });
            return selected.length > 0 ? selected.join(',') : null;
        }

        async function fetchData() {
            const typeParam = getTypeFilterParams();
            const sourceParam = getSourceFilterParams();
            const maxNodesSlider = document.getElementById('rel-max-nodes-slider');
            const maxNodes = maxNodesSlider ? parseInt(maxNodesSlider.value, 10) : 100;
            const url = new URL('/relationship/strength', window.location.origin);
            if (typeParam) url.searchParams.set('types', typeParam);
            if (sourceParam) url.searchParams.set('sources', sourceParam);
            url.searchParams.set('max_nodes', String(maxNodes));
            const response = await fetch(url.toString());
            if (!response.ok) throw new Error('Failed to load relationship data');
            return response.json();
        }

        function updateGraph() {
            if (!cy) return;
            const slider = document.getElementById('rel-filter-slider');
            const sizeSlider = document.getElementById('rel-size-slider');
            if (!slider || !sizeSlider ) return;
            const threshold = parseInt(slider.value);
            const baseSize = parseFloat(sizeSlider.value);
            const hub = cy.getElementById('0');

            cy.edges().forEach(e => {
                if (e.data('strength') < threshold) e.addClass('hidden');
                else e.removeClass('hidden');
            });

            cy.nodes().forEach(n => {
                const hasVisibleEdge = n.connectedEdges().some(e => !e.hasClass('hidden'));
                if (!hasVisibleEdge) n.addClass('hidden');
                else n.removeClass('hidden');
            });

            const visible = cy.nodes().filter(n => !n.hasClass('hidden'));
            if (visible.length > 0) {
                const degrees = visible.map(n => n.connectedEdges().filter(e => !e.hasClass('hidden')).length);
                const min = Math.min(...degrees), max = Math.max(...degrees);
                const maxSize = baseSize * 4;
                visible.forEach(n => {
                    const deg = n.connectedEdges().filter(e => !e.hasClass('hidden')).length;
                    let s = baseSize;
                    if(max !== min) s = baseSize + (deg - min) * (maxSize - baseSize) / (max - min);
                    n.style({'width': s, 'height': s});
                });
            }
        }

        function reLayout() {
            if (!cy) return;
            updateGraph();
            const hub = cy.getElementById('{{full_name}}');
            hub.unlock();
            hub.position({ x: cy.width() / 2, y: cy.height() / 2 });
            hub.lock();
            const layout = cy.layout({ name: 'cose', animate: true, fit: false, nodeRepulsion: () => 800000, gravity: 2, eles: cy.elements(':visible') });
            layout.one('layoutstop', () => { cy.animate({ center: { eles: hub }, zoom: 0.7, duration: 800 }); });
            layout.run();
        }

        function resetView() {
            if (cy) cy.animate({ fit: { eles: cy.elements(':visible'), padding: 50 }, duration: 500 });
        }

        function setupEvents() {
            const balloon = document.getElementById('rel-balloon');
            const searchInput = document.getElementById('rel-search-input');
            const filterSlider = document.getElementById('rel-filter-slider');
            const sizeSlider = document.getElementById('rel-size-slider');
            const strVal = document.getElementById('rel-str-val');
            const sizeVal = document.getElementById('rel-size-val');
            if (!balloon || !cy) return;

            if (searchInput) {
                const doSearch = () => {
                    const text = searchInput.value.toLowerCase().trim();
                    if (!text) return;
                    const found = cy.nodes().filter(n => n.data('name').toLowerCase().includes(text));
                    if (found.length > 0) { cy.animate({ center: { eles: found[0] }, zoom: 1.2, duration: 400 }); found[0].select(); }
                };
                searchInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });
                searchInput.addEventListener('blur', doSearch);
            }

            cy.on('mouseover', 'node', function(e) {
                const node = e.target;
                const neighborhood = node.closedNeighborhood();
                cy.elements().addClass('faded');
                neighborhood.removeClass('faded').addClass('highlight');
            });

            cy.on('mouseout', 'node', function() {
                cy.elements().removeClass('faded highlight');
            });

            function positionBalloon(renderedPos) {
                const container = document.querySelector('.rel-cy-container');
                if (!container) return;
                const rect = container.getBoundingClientRect();
                balloon.style.top = (renderedPos.y - rect.top - 40) + 'px';
                balloon.style.left = (renderedPos.x - rect.left + 10) + 'px';
            }

            cy.on('tap', 'edge', function(e) {
                const edge = e.target;
                clearTimeout(hideTimeout);
                cy.edges().unselect();
                edge.select();
                balloon.innerHTML = `<strong>Strength: ${edge.data('strength')}/10</strong>`;
                balloon.style.display = 'block';
                positionBalloon(e.renderedPosition);
                hideTimeout = setTimeout(() => { balloon.style.display = 'none'; edge.unselect(); }, 3000);
            });

            const CONTACT_TYPES = ['friend', 'family', 'colleague', 'acquaintance', 'business', 'social', 'promotional', 'spam', 'important', 'unknown'];
            cy.on('tap', 'node', function(e) {
                const node = e.target;
                balloon.style.display = 'none';
                const detailsPanel = document.getElementById('rel-node-details');
                if (!detailsPanel) return;
                const nodeId = node.id();
                const nodeName = node.data('name');
                const currentType = node.data('contact_type') || 'unknown';
                const edges = node.connectedEdges().filter(e => !e.hasClass('hidden'));
                const connections = edges.map(edge => {
                    const other = edge.source().id() === nodeId ? edge.target() : edge.source();
                    return { name: other.data('name'), strength: edge.data('strength') };
                });
                const counts = [
                    ['Email', node.data('num_emails')],
                    ['Facebook', node.data('num_facebook')],
                    ['WhatsApp', node.data('num_whatsapp')],
                    ['SMS/iMessage', (node.data('num_sms') || 0) + (node.data('num_imessages') || 0)],
                    ['Instagram', node.data('num_instagram')]
                ].filter(([, n]) => n != null && n > 0);
                let html = `<strong>${nodeName}</strong><br>`;
                if (connections.length > 0) {
                    connections.forEach(c => {
                        html += `<span style="color:#666">Connection strength ${c.strength}/10</span><br/>`;
                    });
                }
                if (counts.length > 0) {
                    html += '<div style="margin-top: 0.5em; font-size: 1em; color: #555;">';
                    html += '<label style="display:block; margin-top: 0.75em; font-weight: 600;">Number of Messages:</label>';
                    html += '<ul style="margin: 0.5em 0 0 1.2em; padding: 0;">';
                    html += counts.map(([label, n]) => `<li>${label}: ${n}</li>`).join(' ');
                    html += '</ul>';
                }
 
                if (nodeId !== '0') {
                    html += '<label style="display:block; margin-top: 0.75em; font-weight: 600;">Contact Type:</label>';
                    html += '<div id="rel-contact-type-radios" style="margin-top: 0.25em; display: flex; flex-wrap: wrap; gap: 0.5em;">';
                    CONTACT_TYPES.forEach(t => {
                        const label = t.charAt(0).toUpperCase() + t.slice(1);
                        const checked = t === currentType ? ' checked' : '';
                        html += `<label style="display: inline-flex; align-items: center; gap: 0.25em; cursor: pointer;"><input type="radio" name="rel-contact-type" value="${t}"${checked}> ${label}</label>`;
                    });
                    html += '</div>';
                }
                detailsPanel.innerHTML = html;
                if (nodeId !== '0') {
                    let lastSavedType = currentType;
                    const radioContainer = document.getElementById('rel-contact-type-radios');
                    if (radioContainer) {
                        radioContainer.addEventListener('change', async function(e) {
                            const radio = e.target;
                            if (radio.type !== 'radio' || radio.name !== 'rel-contact-type') return;
                            const newType = radio.value;
                            if (newType === lastSavedType) return;
                            try {
                                const res = await fetch('/contacts/update-classification', {
                                    method: 'PATCH',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ name: nodeName, classification: newType })
                                });
                                if (!res.ok) {
                                    const err = await res.json().catch(() => ({}));
                                    const msg = Array.isArray(err.detail) ? err.detail.map(d => d.msg || JSON.stringify(d)).join('; ') : (err.detail || res.statusText);
                                    throw new Error(msg);
                                }
                                node.data('contact_type', newType);
                                lastSavedType = newType;
                                if (typeof UI !== 'undefined' && UI.displayError) UI.displayError(null);
                            } catch (err) {
                                if (typeof UI !== 'undefined' && UI.displayError) {
                                    UI.displayError('Failed to save: ' + (err.message || 'Unknown error'));
                                } else {
                                    alert('Failed to save: ' + (err.message || 'Unknown error'));
                                }
                                const prevRadio = radioContainer.querySelector(`input[value="${lastSavedType}"]`);
                                if (prevRadio) prevRadio.checked = true;
                            }
                        });
                    }
                }
            });

            cy.on('tap', function(e) {
                if (e.target === cy) {
                    balloon.style.display = 'none';
                    cy.edges().unselect();
                    const detailsPanel = document.getElementById('rel-node-details');
                    if (detailsPanel) {
                        detailsPanel.innerHTML = '<em style="color: #666;">Click a person to view details</em>';
                    }
                }
            });

            if (filterSlider && strVal) filterSlider.oninput = function() { strVal.innerText = this.value; updateGraph(); };
            if (sizeSlider && sizeVal) sizeSlider.oninput = function() { sizeVal.innerText = this.value; updateGraph(); };
            const maxNodesSlider = document.getElementById('rel-max-nodes-slider');
            const maxNodesVal = document.getElementById('rel-max-nodes-val');
            if (maxNodesSlider && maxNodesVal) maxNodesSlider.oninput = function() { maxNodesVal.innerText = this.value; };

        }

        async function initGraph() {
            const container = document.getElementById('rel-cy');
            if (!container || typeof cytoscape === 'undefined') return;
            let data;
            try {
                data = await fetchData();
            } catch (err) {
                console.error('Relationships fetch failed:', err);
                if (typeof UI !== 'undefined' && UI.displayError) UI.displayError('Could not load relationship data: ' + (err.message || 'Unknown error'));
                else alert('Could not load relationship data. Please try again.');
                return;
            }
            const elements = [...data.nodes.map(n => ({data: n})), ...data.links.map(l => ({data: l}))];

            cy = cytoscape({
                container: container,
                elements: elements,
                style: [
                    { selector: 'node', style: { 'background-color': '#4285f4', 'label': 'data(name)', 'font-size': '10px', 'text-valign': 'bottom', 'text-margin-y': 4 } },
                    { selector: 'node[id="0"]', style: { 'background-color': '#1a73e8', 'border-width': 3, 'border-color': '#000', 'z-index': 1000 } },
                    { selector: 'node[contact_type="friend"]', style: { 'background-color': '#4CAF50' } },
                    { selector: 'node[contact_type="family"]', style: { 'background-color': '#E91E63' } },
                    { selector: 'node[contact_type="colleague"]', style: { 'background-color': '#FF9800' } },
                    { selector: 'node[contact_type="acquaintance"]', style: { 'background-color': '#2196F3' } },
                    { selector: 'node[contact_type="business"]', style: { 'background-color': '#607D8B' } },
                    { selector: 'node[contact_type="social"]', style: { 'background-color': '#9C27B0' } },
                    { selector: 'node[contact_type="promotional"]', style: { 'background-color': '#FFC107' } },
                    { selector: 'node[contact_type="spam"]', style: { 'background-color': '#9E9E9E' } },
                    { selector: 'node[contact_type="important"]', style: { 'background-color': '#00BCD4' } },
                    { selector: 'node[contact_type="unknown"]', style: { 'background-color': '#BDBDBD' } },
                    { selector: 'edge', style: { 'width': 'data(strength)', 'line-color': '#e0e0e0', 'curve-style': 'bezier', 'opacity': 0.6 } },
                    { selector: 'edge[source="0"], edge[target="0"]', style: { 'line-color': '#bbdefb' } },
                    { selector: '.hidden', style: { 'display': 'none' } },
                    { selector: 'edge:selected', style: { 'line-color': '#ff5722', 'opacity': 1, 'z-index': 999 } },
                    { selector: '.faded', style: { 'opacity': 0.08, 'text-opacity': 0 } },
                    { selector: '.highlight', style: { 'opacity': 1, 'text-opacity': 1, 'z-index': 9999 } }
                ]
            });

            setupEvents();
            reLayout();
            
        }

        function open() {
            Modals._openModal(DOM.relationshipsModal);
            initGraph();
        }

        function close() {
            if (cy) {
                try { cy.destroy(); } catch (e) { console.debug('Error destroying cytoscape:', e); }
                cy = null;
            }
            clearTimeout(hideTimeout);
            Modals._closeModal(DOM.relationshipsModal);
        }

        function init() {
            if (DOM.closeRelationshipsModalBtn) DOM.closeRelationshipsModalBtn.addEventListener('click', close);
            if (DOM.relationshipsModal) DOM.relationshipsModal.addEventListener('click', (e) => { if (e.target === DOM.relationshipsModal) close(); });
            const fitBtn = document.getElementById('rel-fit-all-btn');
            const applyBtn = document.getElementById('rel-apply-filters-btn');
            if (fitBtn) fitBtn.addEventListener('click', resetView);
            if (applyBtn) {
                applyBtn.addEventListener('click', () => {
                    initGraph();
                    applyBtn.disabled = true;
                });
                const enableApplyOnFilterChange = () => { applyBtn.disabled = false; };
                document.querySelectorAll('.rel-type-cb, .rel-source-cb').forEach(el => {
                    el.addEventListener('change', enableApplyOnFilterChange);
                });
                const maxNodesSlider = document.getElementById('rel-max-nodes-slider');
                if (maxNodesSlider) maxNodesSlider.addEventListener('input', enableApplyOnFilterChange);
            }
        }

        return { init, open, close };
})();


