(function () {
    "use strict";

    function getPreference(name, fallback = null) {
        if (window.BSPortalPreferences) {
            return window.BSPortalPreferences.get(name, fallback);
        }
        return fallback;
    }

    function setPreference(name, value) {
        if (window.BSPortalPreferences) {
            window.BSPortalPreferences.set(name, value);
        }
    }

    function initTicketWorkspacePreference() {
        const workspace = document.querySelector("[data-shit-workspace]");
        if (!workspace) {
            return;
        }

        const viewMode = workspace.dataset.viewMode;
        if (viewMode === "board" || viewMode === "list") {
            setPreference("shit-view", viewMode);
        }
    }

    function initAssetPickers() {
        document.querySelectorAll("[data-asset-picker]").forEach((picker) => {
            const filter = picker.querySelector("[data-asset-filter]");
            const select = picker.querySelector("select");
            const context = picker.querySelector("[data-asset-context]");
            if (!filter || !select) {
                return;
            }

            const originalOptions = Array.from(select.options).map((option) => ({
                value: option.value,
                text: option.textContent,
            }));

            function currentSelection() {
                return new Set(
                    Array.from(select.selectedOptions)
                        .map((option) => option.value)
                        .filter(Boolean)
                );
            }

            function updateContext() {
                if (!context) {
                    return;
                }
                const selected = Array.from(select.selectedOptions).filter(
                    (option) => option.value
                );
                if (!selected.length) {
                    context.textContent = select.multiple
                        ? "No BAM assets selected."
                        : "No BAM asset selected.";
                    return;
                }
                if (select.multiple) {
                    if (selected.length === 1) {
                        context.textContent = selected[0].textContent;
                    } else {
                        context.textContent = `${selected.length} BAM assets selected.`;
                    }
                    return;
                }
                context.textContent = selected[0].textContent;
            }

            function applyFilter() {
                const query = filter.value.trim().toLowerCase();
                const selectedValues = currentSelection();
                select.replaceChildren();

                originalOptions.forEach((item) => {
                    if (
                        !item.value
                        || !query
                        || item.text.toLowerCase().includes(query)
                        || selectedValues.has(item.value)
                    ) {
                        const option = new Option(item.text, item.value);
                        option.selected = selectedValues.has(item.value);
                        select.add(option);
                    }
                });
                updateContext();
            }

            filter.addEventListener("input", applyFilter);
            select.addEventListener("change", updateContext);
            updateContext();
        });
    }

    function initBoard() {
        const boardShell = document.querySelector("[data-shit-board]");
        if (!boardShell) {
            return;
        }

        const liveRegion = boardShell.querySelector("[data-board-live]");
        let draggedCard = null;
        let sourceDropzone = null;

        function announce(message) {
            if (liveRegion) {
                liveRegion.textContent = message;
            }
        }

        function refreshColumn(column) {
            if (!column) {
                return;
            }
            const dropzone = column.querySelector("[data-dropzone]");
            const count = column.querySelector("[data-column-count]");
            if (!dropzone || !count) {
                return;
            }
            const cards = dropzone.querySelectorAll(".shit-ticket-card");
            count.textContent = String(cards.length);
            const emptyState = dropzone.querySelector("[data-empty-state]");
            if (cards.length && emptyState) {
                emptyState.remove();
            } else if (!cards.length && !emptyState) {
                const empty = document.createElement("div");
                empty.className = "shit-board-empty";
                empty.dataset.emptyState = "";
                empty.textContent = "No tickets";
                dropzone.appendChild(empty);
            }
        }

        function getInsertionPoint(dropzone, pointerY) {
            const cards = Array.from(
                dropzone.querySelectorAll(
                    ".shit-ticket-card:not(.is-dragging)"
                )
            );
            let closest = null;
            let closestOffset = Number.NEGATIVE_INFINITY;

            cards.forEach((card) => {
                const rect = card.getBoundingClientRect();
                const offset = pointerY - rect.top - rect.height / 2;
                if (offset < 0 && offset > closestOffset) {
                    closestOffset = offset;
                    closest = card;
                }
            });
            return closest;
        }

        async function persistMove(card, targetColumn, beforeCard) {
            const tokenInput = card.querySelector(
                "input[name='csrfmiddlewaretoken']"
            );
            if (!tokenInput) {
                throw new Error("CSRF token unavailable. Reload the board and try again.");
            }

            const body = new URLSearchParams();
            body.set("csrfmiddlewaretoken", tokenInput.value);
            body.set("status", targetColumn.dataset.status);
            body.set("reorder", "1");
            body.set(
                "before_ticket_number",
                beforeCard ? beforeCard.dataset.ticketNumber : ""
            );

            const response = await fetch(card.dataset.moveUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: body.toString(),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.ok) {
                throw new Error(data.error || "The ticket move was rejected by the server.");
            }
            return data;
        }

        boardShell.querySelectorAll(".shit-ticket-card[draggable='true']").forEach((card) => {
            card.addEventListener("dragstart", (event) => {
                draggedCard = card;
                sourceDropzone = card.closest("[data-dropzone]");
                card.classList.add("is-dragging");
                event.dataTransfer.effectAllowed = "move";
                event.dataTransfer.setData("text/plain", card.dataset.ticketNumber);
            });

            card.addEventListener("dragend", () => {
                card.classList.remove("is-dragging");
                boardShell.querySelectorAll("[data-dropzone]").forEach((dropzone) => {
                    dropzone.classList.remove("is-drag-over");
                });
                draggedCard = null;
                sourceDropzone = null;
            });
        });

        boardShell.querySelectorAll("[data-dropzone]").forEach((dropzone) => {
            dropzone.addEventListener("dragover", (event) => {
                if (!draggedCard) {
                    return;
                }
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
                dropzone.classList.add("is-drag-over");
                const beforeCard = getInsertionPoint(dropzone, event.clientY);
                const emptyState = dropzone.querySelector("[data-empty-state]");
                if (emptyState) {
                    emptyState.remove();
                }
                if (beforeCard) {
                    dropzone.insertBefore(draggedCard, beforeCard);
                } else {
                    dropzone.appendChild(draggedCard);
                }
            });

            dropzone.addEventListener("dragleave", (event) => {
                if (!dropzone.contains(event.relatedTarget)) {
                    dropzone.classList.remove("is-drag-over");
                }
            });

            dropzone.addEventListener("drop", async (event) => {
                if (!draggedCard) {
                    return;
                }
                event.preventDefault();
                dropzone.classList.remove("is-drag-over");

                const card = draggedCard;
                const targetColumn = dropzone.closest("[data-status]");
                const oldColumn = sourceDropzone ? sourceDropzone.closest("[data-status]") : null;
                const beforeCard = card.nextElementSibling && card.nextElementSibling.classList.contains("shit-ticket-card")
                    ? card.nextElementSibling
                    : null;

                refreshColumn(oldColumn);
                refreshColumn(targetColumn);

                try {
                    const result = await persistMove(card, targetColumn, beforeCard);
                    const statusNode = card.querySelector("[data-card-status]");
                    if (statusNode) {
                        statusNode.textContent = result.status_display;
                    }
                    card.querySelectorAll("select[name='status']").forEach((select) => {
                        select.value = result.status;
                    });
                    card.querySelectorAll("input[name='status']").forEach((input) => {
                        input.value = result.status;
                    });
                    card.className = card.className
                        .split(/\s+/)
                        .filter((name) => !name.startsWith("status-"))
                        .join(" ");
                    card.classList.add(`status-${result.status.toLowerCase()}`);
                    announce(`${result.ticket_number} moved to ${result.status_display}.`);
                } catch (error) {
                    announce(error.message);
                    window.alert(`${error.message}\n\nThe board will reload from the server.`);
                    window.location.reload();
                }
            });
        });
    }

    function initTicketDetailDensity() {
        const detail = document.querySelector("[data-ticket-detail]");
        const header = document.querySelector("[data-ticket-detail-header]");
        if (!detail || !header) {
            return;
        }

        const buttons = Array.from(header.querySelectorAll("[data-detail-density]"));
        const sections = Array.from(detail.querySelectorAll("[data-detail-section]"));
        const compactQuery = window.matchMedia("(max-width: 1180px)");
        const savedFromMarkup = header.dataset.savedDensity;
        const savedFromBrowser = getPreference("shit-detail-density", savedFromMarkup || null);
        let savedDensity = savedFromBrowser === "dense" || savedFromBrowser === "compact"
            ? savedFromBrowser
            : null;

        function applyDensity(mode, preserveDisclosureState) {
            const density = mode === "compact" ? "compact" : "dense";
            detail.dataset.density = density;
            header.dataset.density = density;

            buttons.forEach((button) => {
                button.setAttribute(
                    "aria-pressed",
                    button.dataset.detailDensity === density ? "true" : "false"
                );
            });

            if (density === "dense") {
                sections.forEach((section) => {
                    section.open = true;
                });
            } else if (!preserveDisclosureState) {
                sections.forEach((section, index) => {
                    section.open = index === 0;
                });
            }
        }

        buttons.forEach((button) => {
            button.addEventListener("click", () => {
                savedDensity = button.dataset.detailDensity === "compact"
                    ? "compact"
                    : "dense";
                setPreference("shit-detail-density", savedDensity);
                applyDensity(savedDensity, false);
            });
        });

        function applyResponsiveDefault() {
            if (savedDensity) {
                applyDensity(savedDensity, true);
                return;
            }
            applyDensity(compactQuery.matches ? "compact" : "dense", false);
        }

        if (typeof compactQuery.addEventListener === "function") {
            compactQuery.addEventListener("change", applyResponsiveDefault);
        } else if (typeof compactQuery.addListener === "function") {
            compactQuery.addListener(applyResponsiveDefault);
        }

        applyResponsiveDefault();
    }

    initTicketWorkspacePreference();
    initAssetPickers();
    initBoard();
    initTicketDetailDensity();
}());
