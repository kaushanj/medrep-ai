# Medical Representative Domain

## Domain Overview

MedRep AI supports users who need information about medical products.

Users ask questions about medical products, and answers should be based on information available in real product documents.

The current project focuses on medical product information rather than CRM, sales, inventory, quotation, or administration features.

## Main Domain Concepts

### Medical Product

A medical product is a medicine or healthcare product that a user can ask questions about.

A medical product may be identified by information such as:

- brand name
- generic name
- active ingredient
- strength
- dosage form
- manufacturer

The exact product types supported by MedRep AI are still being defined.

### Product Document

A product document is a real document containing information about a medical product.

Examples may include:

- product information leaflets
- prescribing information
- product catalogs
- official manufacturer documents
- regulatory product documents

The exact document sources used by the project are still being defined.

### Source Document

A source document is the product document containing information that supports an answer.

When MedRep AI provides an answer based on product information, the answer should be traceable to the supporting source document.

The exact source information shown to users is TBD.

### Product Information

Product information is medical or descriptive information about a product contained in a product document.

This information may include:

- product name
- generic name
- active ingredients
- strength
- dosage form
- indications
- dosage
- contraindications
- warnings
- precautions
- adverse effects
- storage information
- manufacturer information

Not every product document is expected to contain every type of information.

### Brand Name

A brand name is the commercial name under which a medical product is marketed.

A product may have a brand name that is different from the name of its active ingredient.

### Generic Name

A generic name identifies the medicine independently of a commercial brand name.

The exact way generic names are represented depends on the product document.

### Active Ingredient

An active ingredient is the substance responsible for the therapeutic effect of a medical product.

A product may contain one or more active ingredients.

### Strength

Strength describes the amount or concentration of an active ingredient in a medical product.

Examples may include values such as:

- 500 mg
- 250 mg / 5 mL

The exact representation depends on the source document.

### Dosage Form

Dosage form describes the physical form in which a medical product is provided.

Examples may include:

- tablet
- capsule
- syrup
- suspension
- injection
- cream

The exact dosage forms supported depend on the product documents.

### Indication

An indication describes the medical condition or purpose for which a product is intended to be used.

Indication information should only be presented when it is supported by the available product documents.

### Dosage

Dosage describes how much of a product should be used and how often, according to the available product information.

Dosage information may depend on factors described in the source document.

MedRep AI should not invent dosage information that is not supported by the product documents.

### Contraindication

A contraindication describes a condition or situation where a medical product should not be used.

Contraindication information should be based on the source product documents.

### Warning

A warning describes important safety information associated with the use of a medical product.

Warnings should only be presented when they are supported by available product information.

### Precaution

A precaution describes information that should be considered before or while using a medical product.

The exact precaution information depends on the source document.

### Adverse Effect

An adverse effect is an unwanted effect associated with the use of a medical product.

Adverse-effect information should be based on the available product documents.

### Storage Information

Storage information describes how a medical product should be stored.

Examples may include temperature or environmental conditions.

The exact storage requirements depend on the source document.

### Manufacturer

The manufacturer is the company or organization responsible for producing the medical product.

Manufacturer information may be present in product documents.

### Supported Answer

A supported answer is an answer that can be traced to relevant information found in the available product documents.

A supported answer should have enough source information for the user to identify where the information came from.

### Unsupported Information

Unsupported information is information that cannot be supported by the available product documents.

Unsupported information should not be presented as if it came from the product documents.

## Domain Relationships

The main domain relationships are:

- A user asks a question about medical product information.
- A medical product may have one or more product documents.
- A product document contains product information.
- A product may contain one or more active ingredients.
- A product may have a brand name and a generic name.
- A product may have a strength and dosage form.
- Product information may contain indications, dosage, contraindications, warnings, precautions, adverse effects, and storage information.
- Product information can support an answer.
- A supported answer should be traceable to one or more source documents.

The exact relationship between products and documents will be refined after the real product document dataset is selected.

## Domain Rules

### DRULE-001 - Use Product Documents as Evidence

Answers about medical products should be based on information available in the product documents.

### DRULE-002 - Do Not Present Unsupported Information as Fact

Information that cannot be supported by the available product documents should not be presented as product-document fact.

### DRULE-003 - Source Traceability

A supported answer should be traceable to the document containing the supporting information.

### DRULE-004 - Missing Information

If suitable supporting information cannot be found, the system should not invent an answer.

### DRULE-005 - Unrelated Questions

Questions unrelated to the available medical product information should not be answered as if the response were supported by the product documents.

### DRULE-006 - Medical Information Must Match the Source

Medical information such as dosage, indication, contraindication, warnings, precautions, and adverse effects should only be presented when supported by the available product documents.

### DRULE-007 - Documents May Differ

Different product documents may contain different types and levels of information.

The system should not assume that every product document contains all domain fields.

## Glossary

**Medical Product**  
A medicine or healthcare product about which the user can ask questions.

**Brand Name**  
The commercial name of a medical product.

**Generic Name**  
The non-brand name used to identify a medicine.

**Active Ingredient**  
A substance responsible for the therapeutic effect of a medical product.

**Strength**  
The amount or concentration of an active ingredient in a product.

**Dosage Form**  
The physical form of the product, such as a tablet, capsule, syrup, or injection.

**Indication**  
A condition or purpose for which a medical product is intended to be used.

**Dosage**  
Information describing how much of a product should be used and how often.

**Contraindication**  
A condition or situation where a product should not be used.

**Warning**  
Important safety information related to the use of a product.

**Precaution**  
Information that should be considered before or during use of a product.

**Adverse Effect**  
An unwanted effect associated with the use of a medical product.

**Storage Information**  
Information describing how a medical product should be stored.

**Manufacturer**  
The company or organization responsible for producing a medical product.

**Product Document**  
A real document containing medical product information.

**Source Document**  
A product document containing information that supports an answer.

**Product Information**  
Information about a medical product contained in available product documents.

**Supported Answer**  
An answer that is backed by relevant information from product documents.

**Unsupported Information**  
Information that cannot be supported by the available product documents.

## Open Questions

- What exact types of medical products will MedRep AI support?
- Which official or trusted sources will be used for the real product documents?
- Will each document represent one product or can a document contain multiple products?
- Can one product have multiple source documents?
- What exact product information is available in the selected real documents?
- What source information should be shown to users?
- Should the source include only the document name, or also page and section information?
- Are there additional product-information concepts required by the real documents?
- Are there domain-specific restrictions on which medical product questions should be answered?