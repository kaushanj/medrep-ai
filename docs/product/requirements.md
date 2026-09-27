# MedRep AI Product Requirements

Status: Draft

## Product Goal

MedRep AI is a small medical product assistant.

The product allows authorized users to ask questions about medical products and receive answers based on available product information.

The main value is to help users find relevant information from product documents quickly without manually searching through multiple documents.

## Target Users

Exact user roles are **TBD**.

The product is intended for authorized users who need to find and understand information about medical products.

## Functional Requirements

### FR-001 - User Authentication

Description:  
The user should be able to sign in before accessing the MedRep AI product assistant.

Acceptance Criteria:
- A user can sign in using Google.
- An unauthenticated user cannot access protected product assistant functionality.
- An authenticated user can access the product assistant.

### FR-002 - Ask Product Questions

Description:  
The user should be able to ask questions about medical products.

Acceptance Criteria:
- A user can enter a question.
- A user can submit the question.
- The system returns a response to the submitted question.

### FR-003 - Answer Using Product Information

Description:  
The system should answer product questions using the available product information.

Acceptance Criteria:
- The system uses relevant available product information when answering a question.
- The answer should be related to the user's question and the available product information.
- The system should not present unsupported information as if it came from the product documents.

### FR-004 - Show Answer Source

Description:  
The user should be able to see which product document was used as a source for an answer.

Acceptance Criteria:
- An answer includes source information when supporting product information is found.
- The source identifies the relevant product document.
- The exact source format shown to the user is **TBD**.

### FR-005 - Handle Missing Product Information

Description:  
The system should handle questions when suitable product information cannot be found.

Acceptance Criteria:
- The system does not invent a product answer when suitable supporting information is unavailable.
- The user receives a controlled fallback response.
- The exact fallback message is **TBD**.

### FR-006 - Handle Unrelated Questions

Description:  
The system should handle questions that are unrelated to the available medical product information.

Acceptance Criteria:
- The system should not provide an unsupported product answer for an unrelated question.
- The user receives an appropriate controlled response.
- The exact response for unrelated questions is **TBD**.

### FR-007 - Product Assistant Chat

Description:  
The user should be able to interact with the product through a simple chat interface.

Acceptance Criteria:
- The user can enter a product question through the chat interface.
- The user can see the returned answer.
- The user can see available source information with the answer.

## Data Requirements

### DR-001 - Product Documents

Description:  
The product requires medical product documents that contain the information used to answer user questions.

Requirements:
- Product information should be available as product documents.
- The initial project uses product catalog PDF documents.
- Documents must contain information that can be used to answer product-related questions.

### DR-002 - Source Information

Description:  
The product requires enough source information to identify the document supporting an answer.

Requirements:
- Each available product document must be identifiable.
- The system must be able to associate an answer with its supporting product document.
- The exact source information displayed to users is **TBD**.

## Non-Functional Product Requirements

### NFR-001 - Grounded Answers

Answers should be based on available product information.

### NFR-002 - Avoid Unsupported Answers

The product should avoid giving answers that are not supported by the available product information.

### NFR-003 - Source Visibility

The product should show source information so users can identify the product document supporting an answer.

### NFR-004 - Authorized Access

Product assistant functionality should only be available to authorized users.

### NFR-005 - Controlled Failure Behavior

When the product cannot find enough information to answer a question, it should return a controlled response instead of inventing an answer.

### NFR-006 - Simple User Experience

The product should provide a simple interface focused on asking product questions and viewing answers and sources.

## Out of Scope

The following functionality is not part of the current product:

- CRM features
- Quotations
- Email automation
- Inventory management
- Sales dashboards
- Complex administration functionality
- Complex document approval workflows
- Large mobile application

## Future Features

### Additional Assistant Actions

Additional assistant capabilities beyond the current product question-and-answer experience may be explored in a later version.

The exact user-facing features are **TBD**.

## Open Questions

- Exact user roles are **TBD**.
- Exact permissions for different user roles are **TBD**.
- Exact source format shown with answers is **TBD**.
- Exact fallback message when supporting information cannot be found is **TBD**.
- Exact response behavior for unrelated questions is **TBD**.
- Whether users need conversation history is **TBD**.
- Whether users need to select or filter specific products before asking a question is **TBD**.
- Future assistant actions beyond product question answering are **TBD**.