// Helper to strip duplicates from arrays quickly
const unique = (arr) => [...new Set(arr)];

export class SearchEngine {
    constructor() {
        this.inventoryData = [];
        this.moleculeData = [];
    }

    // Loads the data into the engine (called from api.js or app.js)
    loadData(inventory, molecules) {
        this.inventoryData = inventory;
        this.moleculeData = molecules;
    }

    // --- RESTORED: DEBOUNCE & RECENT SEARCHES ---
    debounce(func, delay = 50) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    }

    getRecents() {
        const recents = localStorage.getItem('pharm_recent_searches');
        return recents ? JSON.parse(recents) : [];
    }

    saveRecent(query) {
        if (!query) return;
        const cleanQuery = query.trim();
        if (cleanQuery === '') return;
        
        let recents = this.getRecents();
        // Remove it if it exists so we can move it to the top
        recents = recents.filter(item => item.toLowerCase() !== cleanQuery.toLowerCase());
        
        // Add to the front
        recents.unshift(cleanQuery);
        
        // Keep only top 5 recent searches
        if (recents.length > 5) {
            recents.pop();
        }
        
        localStorage.setItem('pharm_recent_searches', JSON.stringify(recents));
    }
    
    // Safety alias in case app.js uses addRecent instead of saveRecent
    addRecent(query) { this.saveRecent(query); }

    // --- SMART RANKING ALGORITHM ---
    _rankMatches(dataArray, query, primaryField, secondaryField = null) {
        return dataArray.filter(item => {
            // First, find everything that contains the letters
            const val1 = String(item[primaryField] || '').toLowerCase();
            const val2 = secondaryField ? String(item[secondaryField] || '').toLowerCase() : '';
            return val1.includes(query) || val2.includes(query);
        }).sort((a, b) => {
            // Now, RANK them by relevance
            const a1 = String(a[primaryField] || '').toLowerCase();
            const b1 = String(b[primaryField] || '').toLowerCase();
            
            const aStarts = a1.startsWith(query);
            const bStarts = b1.startsWith(query);
            
            // Priority 1: If 'A' starts with the query but 'B' doesn't, 'A' wins.
            if (aStarts && !bStarts) return -1;
            if (!aStarts && bStarts) return 1;
            
            // Priority 2: If both start with it (or neither do), the shorter string wins.
            return a1.length - b1.length;
        }).slice(0, 3); // Finally, slice ONLY the top 3 gold-medal winners.
    }

    // --- CORE RESOLUTION ENGINE ---
    resolveContext(query) {
        if (!query) return [];
        const cleanQuery = query.toLowerCase().trim();
        let contexts = [];

        // GUESS 1: Did they type a BRAND?
        const matchedProducts = this._rankMatches(this.inventoryData, cleanQuery, 'Brand_Name', 'Variant_Name');

        if (matchedProducts.length > 0) {
            let linkedMols = [];
            matchedProducts.forEach(prod => linkedMols.push(...this._getLinkedMolecules(prod)));
            
            contexts.push({
                guessType: 'Brand',
                matchedText: matchedProducts[0].Brand_Name, // The #1 highest ranked match
                resolutions: {
                    'APIs Present': unique(linkedMols.map(m => m.Molecule_Name)).join(', ') || 'N/A',
                    'Classes': unique(linkedMols.map(m => m.Pharmacological_Class)).join(', ') || 'N/A',
                    'Indications': unique(linkedMols.map(m => m.Indications)).join(', ') || 'N/A'
                },
                productId: matchedProducts[0].Product_ID
            });
        }

        // GUESS 2: Did they type an API?
        const apiMatches = this._rankMatches(this.moleculeData, cleanQuery, 'Molecule_Name');
        if (apiMatches.length > 0) {
            let linkedBrands = [];
            apiMatches.forEach(api => linkedBrands.push(...this._getLinkedProducts(api)));
            
            const uniqueBrands = unique(linkedBrands.map(b => b.Brand_Name));
            let brandDisplay = uniqueBrands.slice(0, 10).join(', '); 
            if (uniqueBrands.length > 10) brandDisplay += ` ... (+${uniqueBrands.length - 10} more)`;

            contexts.push({
                guessType: 'API',
                matchedText: apiMatches[0].Molecule_Name,
                resolutions: {
                    'Found in Brands': brandDisplay || 'No brands registered',
                    'Classes': unique(apiMatches.map(m => m.Pharmacological_Class)).join(', ') || 'N/A',
                    'Indications': unique(apiMatches.map(m => m.Indications)).join(', ') || 'N/A'
                }
            });
        }

        // GUESS 3: Did they type a CLASS?
        const classMatches = this._rankMatches(this.moleculeData, cleanQuery, 'Pharmacological_Class');
        if (classMatches.length > 0) {
            let linkedBrands = [];
            classMatches.forEach(cls => linkedBrands.push(...this._getLinkedProducts(cls)));
            
            const uniqueBrands = unique(linkedBrands.map(b => b.Brand_Name));
            let brandDisplay = uniqueBrands.slice(0, 8).join(', ');
            if (uniqueBrands.length > 8) brandDisplay += ` (+${uniqueBrands.length - 8} more)`;

            contexts.push({
                guessType: 'Class',
                matchedText: classMatches[0].Pharmacological_Class,
                resolutions: {
                    'Related APIs': unique(classMatches.map(m => m.Molecule_Name)).join(', ') || 'N/A',
                    'Found in Brands': brandDisplay || 'N/A'
                }
            });
        }

        // GUESS 4: Did they type an INDICATION?
        const indMatches = this._rankMatches(this.moleculeData, cleanQuery, 'Indications');
        if (indMatches.length > 0) {
            let linkedBrands = [];
            indMatches.forEach(ind => linkedBrands.push(...this._getLinkedProducts(ind)));
            
            const uniqueBrands = unique(linkedBrands.map(b => b.Brand_Name));
            let brandDisplay = uniqueBrands.slice(0, 8).join(', ');
            if (uniqueBrands.length > 8) brandDisplay += ` (+${uniqueBrands.length - 8} more)`;

            contexts.push({
                guessType: 'Indication',
                matchedText: cleanQuery,
                resolutions: {
                    'Treating APIs': unique(indMatches.map(m => m.Molecule_Name)).join(', ') || 'N/A',
                    'Found in Brands': brandDisplay || 'N/A'
                }
            });
        }

        return contexts;
    }

    // --- STRICT ARRAY MATCHING UTILITIES ---
    _getLinkedMolecules(product) {
        if (!product || !product['Molecule(s)']) return [];
        // Strictly splits by comma and checks precise text to avoid false partial matches
        const productApis = String(product['Molecule(s)']).split(',').map(api => api.trim().toLowerCase());
        
        return this.moleculeData.filter(m => 
            m.Molecule_Name && productApis.includes(String(m.Molecule_Name).toLowerCase())
        );
    }

    _getLinkedProducts(molecule) {
        if (!molecule || !molecule.Molecule_Name) return [];
        const targetApi = String(molecule.Molecule_Name).trim().toLowerCase();
        
        return this.inventoryData.filter(p => {
            if (!p['Molecule(s)']) return false;
            const productApis = String(p['Molecule(s)']).split(',').map(api => api.trim().toLowerCase());
            return productApis.includes(targetApi);
        });
    }
}