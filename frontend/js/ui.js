// frontend/js/ui.js

export class PharmUI {
    constructor() {
        // Grab all our HTML elements once
        this.loadingState = document.getElementById("loading-state");
        this.dashboardContent = document.getElementById("dashboard-content");
        this.loadingText = document.getElementById("loading-text");
        this.spinner = document.querySelector(".spinner");
        
        this.tableBody = document.getElementById("table-body");
        this.resultsContainer = document.getElementById("search-results");
        this.recentContainer = document.getElementById("recent-searches-container");
        this.searchBox = document.getElementById("search-box");
        
        this.modal = document.getElementById("modal");
        this.modalDetails = document.getElementById("modal-details");
        
        this.initClock();
        this.bindEvents();
    }

    // --- VIEW CONTROLLERS ---

    showDashboard() {
        this.loadingState.style.display = "none";
        this.dashboardContent.style.display = "block";
    }

    showError(message) {
        this.loadingText.innerText = message;
        if (this.spinner) this.spinner.style.display = "none";
    }

    updateStats(inventory, molecules) {
        const manufacturers = new Set(inventory.map(item => item.Manufacturer_Name).filter(Boolean));
        const uniqueClasses = new Set(molecules.map(item => item.Pharmacological_Class).filter(Boolean));
        const uniqueBrands = new Set(inventory.map(item => item.Brand_Name).filter(Boolean));
        const uniqueForms = new Set(inventory.map(item => item.Dosage_Form).filter(Boolean));
        
        document.getElementById("stat-inventory").innerText = inventory.length;
        document.getElementById("stat-molecules").innerText = molecules.length;
        document.getElementById("stat-manufacturers").innerText = manufacturers.size;
        document.getElementById("stat-classes").innerText = uniqueClasses.size;
        document.getElementById("stat-brands").innerText = uniqueBrands.size;
        document.getElementById("stat-forms").innerText = uniqueForms.size;
    }

    // --- RENDERERS ---

    renderTable(results) {
        this.tableBody.innerHTML = "";
        
        if (results.length === 0) {
            this.tableBody.innerHTML = "<tr><td colspan='6' style='text-align:center; padding: 30px; color: #6b7280;'>No matching records found in the database.</td></tr>";
        } else {
            results.forEach(item => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>${item.Brand_Name || ''}</strong></td>
                    <td>${item.Variant_Name || ''}</td>
                    <td>${item['Strength(s)'] || ''}</td>
                    <td>${item.Dosage_Form || ''}</td>
                    <td>${item.Manufacturer_Name || ''}</td>
                    <td><button class="btn-view" data-id="${item.Product_ID}">View Info</button></td>
                `;
                this.tableBody.appendChild(tr);
            });
        }
        this.resultsContainer.style.display = "block";
    }

    renderRecents(recents, onTagClick) {
        if (recents.length === 0 || this.searchBox.value.trim() !== "") {
            this.recentContainer.style.display = "none";
            return;
        }

        this.recentContainer.innerHTML = '<span style="font-size: 0.85rem; color: #9ca3af; font-weight: 500;">Recent:</span>';
        
        recents.forEach(query => {
            const tag = document.createElement("span");
            tag.className = "recent-tag";
            tag.innerText = query;
            tag.onclick = () => onTagClick(query);
            this.recentContainer.appendChild(tag);
        });
        
        this.recentContainer.style.display = "flex";
    }

    renderModal(product, moleculeData) {
        if (!product) return;
        
        this.modalDetails.innerHTML = `<h3>${product.Brand_Name}</h3><p style="color:#6b7280; margin-top:0;">${product.Variant_Name} | ${product.Manufacturer_Name}</p>`;
        
        const moleculeIds = String(product['Molecule_ID(s)']).split(',').map(id => id.trim());
        
        moleculeIds.forEach(id => {
            const mol = moleculeData.find(m => m.Molecule_ID === id);
            if (mol) {
                this.modalDetails.innerHTML += `
                    <div class="molecule-card">
                        <h4>${mol.Molecule_Name}</h4>
                        <p><strong>Pharmacological Class:</strong> ${mol.Pharmacological_Class || 'N/A'}</p>
                        <p><strong>Indications:</strong> ${mol.Indications || 'N/A'}</p>
                        <p><strong>Side Effects:</strong> ${mol.Side_Effects || 'N/A'}</p>
                        <p><strong>Contraindications:</strong> ${mol.Contraindications || 'N/A'}</p>
                    </div>
                `;
            }
        });
        
        this.modal.style.display = "flex";
    }

    // --- EVENT LISTENERS & UTILS ---

    bindEvents() {
        // Event Delegation for Table Buttons (Much cleaner than inline onclick)
        this.tableBody.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-view')) {
                const productId = e.target.getAttribute('data-id');
                if (this.onViewClick) this.onViewClick(productId);
            }
        });

        // Modal Close Logic
        const closeBtn = document.querySelector(".close-btn");
        if (closeBtn) closeBtn.onclick = () => { this.modal.style.display = "none"; };
        
        window.onclick = (e) => {
            if (e.target === this.modal) this.modal.style.display = "none";
        };
    }

    initClock() {
        const updateClock = () => {
            const now = new Date();
            document.getElementById('live-datetime').innerText = now.toLocaleString();
        };
        updateClock();
        setInterval(updateClock, 1000);
    }
}

export function renderContextualDropdown(query, SearchEngineInstance) {
    const dropdown = document.getElementById("autocomplete-dropdown");
    
    if (query.trim() === "") {
        dropdown.style.display = "none";
        return;
    }

    // Ask the Engine for its Guesses
    const contexts = SearchEngineInstance.resolveContext(query);
    dropdown.innerHTML = "";

    if (contexts.length === 0) {
        dropdown.innerHTML = '<div class="guess-block"><div class="guess-match" style="color:#6b7280;">No explicit category matches... Press Enter to deep search.</div></div>';
        dropdown.style.display = "block";
        return;
    }

    contexts.forEach(ctx => {
        const block = document.createElement("div");
        block.className = "guess-block";
        
        let resolutionsHtml = "";
        for (const [key, value] of Object.entries(ctx.resolutions)) {
            resolutionsHtml += `<div class="res-item"><strong>${key}:</strong> ${value}</div>`;
        }

        const regex = new RegExp(`(${query})`, "gi");
        const highlightedText = ctx.matchedText.replace(regex, '<span class="auto-highlight">$1</span>');

        block.innerHTML = `
            <div class="guess-header">
                <span class="guess-badge">Matches ${ctx.guessType}</span>
                <span class="guess-match">${highlightedText}</span>
            </div>
            <div class="guess-resolutions">
                ${resolutionsHtml}
            </div>
        `;

        block.onclick = () => {
            dropdown.style.display = "none";
            document.getElementById("search-box").value = ctx.matchedText;
            SearchEngineInstance.saveRecent(ctx.matchedText);
            
            // NOTE: Replace 'renderMainTable' with whatever your main table rendering function is named in ui.js!
            // renderMainTable(ctx.matchedText); 
        };

        dropdown.appendChild(block);
    });

    dropdown.style.display = "block";
}