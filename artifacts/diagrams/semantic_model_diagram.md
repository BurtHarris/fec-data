# Semantic Model Diagram with Additional Fact Tables

```mermaid
diagram TD
    subgraph Facts
        FACT1["Contributions Fact Table"]
        FACT2["Disbursements Fact Table"]
        FACT3["Transfers Fact Table"]
        FACT4["Raising Fact Table"]
        FACT5["Spending Fact Table"]
        FACT6["Loans and Debts Fact Table"]
        FACT7["Filings Fact Table"]
    end

    subgraph Dimensions
        DIM1["Candidate Dimension"]
        DIM2["Committee Dimension"]
        DIM3["Election Dimension"]
        DIM4["Time Dimension"]
        DIM5["Party Dimension"]
        DIM6["Transaction Code Dimension"]
        DIM7["Office Dimension"]
        DIM8["Incumbent Status Dimension"]
        DIM9["Candidate Status Dimension"]
        DIM10["Candidate-Committee Linkage Dimension"]
    end

    %% Fact-to-Dimension Relationships
    FACT1 --> DIM1
    FACT1 --> DIM2
    FACT1 --> DIM3
    FACT1 --> DIM4
    FACT1 --> DIM5
    FACT1 --> DIM6

    FACT2 --> DIM1
    FACT2 --> DIM2
    FACT2 --> DIM4

    FACT3 --> DIM2
    FACT3 --> DIM4

    FACT4 --> DIM1
    FACT4 --> DIM2
    FACT4 --> DIM4

    FACT5 --> DIM1
    FACT5 --> DIM2
    FACT5 --> DIM4

    FACT6 --> DIM1
    FACT6 --> DIM2
    FACT6 --> DIM4

    FACT7 --> DIM2
    FACT7 --> DIM4
    FACT7 --> DIM5
    FACT7 --> DIM6

    %% Dimension-to-Dimension Relationships
    DIM1 --> DIM7
    DIM1 --> DIM8
    DIM1 --> DIM9
    DIM2 --> DIM10

    %% Styling
    classDef dim fill:#333,stroke:#000,stroke-width:2px,color:#fff;
    classDef fact fill:#555,stroke:#000,stroke-width:2px,color:#fff;

    class DIM1,DIM2,DIM3,DIM4,DIM5,DIM6,DIM7,DIM8,DIM9,DIM10 dim;
    class FACT1,FACT2,FACT3,FACT4,FACT5,FACT6,FACT7 fact;
```