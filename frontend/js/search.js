// frontend/js/search.js

export class PharmSearchEngine {
    constructor() {
        this.unifiedIndex = [];
        this.inventoryData = [];
        this.moleculeData = [];
        this.recentKey = 'pharmDB_recent_searches';
    }

    /**
     * 1. THE INDEXER: Builds the deep-search string using Hybrid Matching
     */
    buildIndex(inventoryData, moleculeData) {
        this.inventoryData = inventoryData || [];
        this.moleculeData = moleculeData || [];

        this.unifiedIndex = this.inventoryData.map(product => {
            // Ask our new Hybrid matcher to find the molecules via text or ID
            const linkedMols = this._getLinkedMolecules(product);
            
            let apis = [], classes = [], indications = [], sideEffects = [];
            
            linkedMols.forEach(mol => {
                apis.push(mol.Molecule_Name || '');
                classes.push(mol.Pharmacological_Class || '');
                indications.push(mol.Indications || '');
                sideEffects.push(mol.Side_Effects || '');
            });

            // The deep-search string now safely holds ALL linked medical data
            const searchString = `
                ${product.Brand_Name || ''} ${product.Variant_Name || ''} ${product.Manufacturer_Name || ''}
                ${apis.join(' ')} ${classes.join(' ')} 
                ${indications.join(' ')} ${sideEffects.join(' ')}
            `.toLowerCase();

            return { originalProduct: product, _searchString: searchString };
        });
        console.log(`[Search Engine] Index rebuilt with Hybrid Matching! ${this.unifiedIndex.length} products indexed.`);
    }

    /**
     * 2. COMPLETE SEARCH (Main Table)
     */
    search(query) {
        if (!query || query.trim() === '') return [];
        const cleanQuery = query.toLowerCase().trim();
        return this.unifiedIndex
            .filter(item => item._searchString.includes(cleanQuery))
            .map(item => item.originalProduct);
    }

    /**
     * 3. THE INTENT RESOLVER (Smart Aggregation)
     */
    resolveContext(query) {
        if (!query || query.trim() === '') return [];
        const cleanQuery = query.toLowerCase().trim();

        let contexts = [];
        const unique = (arr) => [...new Set(arr.filter(Boolean))];

        // GUESS 1: Did they type a BRAND?
        const matchedProducts = this.inventoryData.filter(p => 
            String(p.Brand_Name).toLowerCase().includes(cleanQuery) || 
            String(p.Variant_Name).toLowerCase().includes(cleanQuery)
        );

        if (matchedProducts.length > 0) {
            let linkedMols = [];
            matchedProducts.forEach(prod => linkedMols.push(...this._getLinkedMolecules(prod)));
            
            contexts.push({
                guessType: 'Brand',
                matchedText: matchedProducts[0].Brand_Name,
                resolutions: {
                    'APIs Present': unique(linkedMols.map(m => m.Molecule_Name)).join(', ') || 'N/A',
                    'Classes': unique(linkedMols.map(m => m.Pharmacological_Class)).join(', ') || 'N/A',
                    'Indications': unique(linkedMols.map(m => m.Indications)).join(', ') || 'N/A'
                },
                productId: matchedProducts[0].Product_ID
            });
        }

        // GUESS 2: Did they type an API?
        const apiMatches = this.moleculeData.filter(m => String(m.Molecule_Name).toLowerCase().includes(cleanQuery));
        if (apiMatches.length > 0) {
            let linkedBrands = [];
            // Pass the entire API object so our hybrid matcher can check its name
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
        const classMatches = this.moleculeData.filter(m => String(m.Pharmacological_Class).toLowerCase().includes(cleanQuery));
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
        const indMatches = this.moleculeData.filter(m => String(m.Indications).toLowerCase().includes(cleanQuery));
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

    // --- NEW: STRICT HYBRID MATCHING UTILITIES ---

    _getLinkedMolecules(product) {
        let matchedMolecules = [];

        // 1. PRIMARY: Split your clean API names into a strict array
        const pNames = String(product['Molecule(s)'] || '').split(',').map(n => n.trim().toLowerCase());
        
        // 2. FALLBACK: Split the IDs if they ever exist
        const pIds = String(product['Molecule_ID(s)'] || product['Molecule_ID'] || '').split(',').map(id => id.trim().toLowerCase());

        this.moleculeData.forEach(mol => {
            const molName = String(mol.Molecule_Name || '').trim().toLowerCase();
            const molId = String(mol.Molecule_ID || '').trim().toLowerCase();

            // Strict Exact Match: Does the exact API name exist in the product's API array?
            const matchByName = molName !== '' && pNames.includes(molName);
            const matchById = molId !== '' && pIds.includes(molId);

            if (matchByName || matchById) {
                matchedMolecules.push(mol);
            }
        });

        // Return unique values to prevent duplicates
        return [...new Set(matchedMolecules)];
    }

    _getLinkedProducts(molecule) {
        const molName = String(molecule.Molecule_Name || '').trim().toLowerCase();
        const molId = String(molecule.Molecule_ID || '').trim().toLowerCase();

        return this.inventoryData.filter(p => {
            // Split the product's columns into exact arrays
            const pNames = String(p['Molecule(s)'] || '').split(',').map(n => n.trim().toLowerCase());
            const pIds = String(p['Molecule_ID(s)'] || p['Molecule_ID'] || '').split(',').map(id => id.trim().toLowerCase());

            const matchByName = molName !== '' && pNames.includes(molName);
            const matchById = molId !== '' && pIds.includes(molId);

            return matchByName || matchById;
        });
    }
    
    // --- CACHE & UTILITIES ---
    saveRecent(query) {
        if (!query || query.trim() === '') return;
        const cleanQuery = query.toLowerCase().trim();
        let recents = this.getRecents();
        recents = recents.filter(item => item !== cleanQuery);
        recents.unshift(cleanQuery);
        if (recents.length > 5) recents.pop();
        localStorage.setItem(this.recentKey, JSON.stringify(recents));
    }

    getRecents() {
        const stored = localStorage.getItem(this.recentKey);
        return stored ? JSON.parse(stored) : [];
    }

    debounce(func, delay) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    }
}