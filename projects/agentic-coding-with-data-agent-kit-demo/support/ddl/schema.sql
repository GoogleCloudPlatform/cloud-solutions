-- DDL Schema for Spanner Ticket Tracking System with Graph and Vector Search

CREATE TABLE Tickets (
  TicketId STRING(36) NOT NULL,
  Title STRING(256) NOT NULL,
  Description STRING(MAX),
  Priority STRING(20) NOT NULL,
  Status STRING(20) NOT NULL,
  DescriptionEmbedding ARRAY<FLOAT32>(vector_length=>768),
  CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
  UpdatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true)
) PRIMARY KEY (TicketId);

CREATE TABLE TicketBlocks (
  BlockerTicketId STRING(36) NOT NULL,
  BlockedTicketId STRING(36) NOT NULL,
  CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
  CONSTRAINT FK_Blocks_Blocker FOREIGN KEY (BlockerTicketId) REFERENCES Tickets (TicketId),
  CONSTRAINT FK_Blocks_Blocked FOREIGN KEY (BlockedTicketId) REFERENCES Tickets (TicketId)
) PRIMARY KEY (BlockerTicketId, BlockedTicketId);

CREATE TABLE TicketCauses (
  CauserTicketId STRING(36) NOT NULL,
  CausedTicketId STRING(36) NOT NULL,
  CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
  CONSTRAINT FK_Causes_Causer FOREIGN KEY (CauserTicketId) REFERENCES Tickets (TicketId),
  CONSTRAINT FK_Causes_Caused FOREIGN KEY (CausedTicketId) REFERENCES Tickets (TicketId)
) PRIMARY KEY (CauserTicketId, CausedTicketId);

-- Secondary Indexes on Edge Tables to optimize GQL graph traversals
CREATE INDEX Index_TicketBlocks_BlockedTicketId ON TicketBlocks (BlockedTicketId);
CREATE INDEX Index_TicketCauses_CausedTicketId ON TicketCauses (CausedTicketId);

-- Vector Search Index for ticket descriptions (null-filtered)
CREATE VECTOR INDEX TicketsDescriptionIndex
ON Tickets (DescriptionEmbedding)
STORING (Title, Priority, Status)
WHERE DescriptionEmbedding IS NOT NULL
OPTIONS (
  distance_type = 'COSINE'
);

-- Property Graph definition
CREATE PROPERTY GRAPH TicketGraph
  NODE TABLES (
    Tickets
  )
  EDGE TABLES (
    TicketBlocks
      SOURCE KEY (BlockerTicketId) REFERENCES Tickets (TicketId)
      DESTINATION KEY (BlockedTicketId) REFERENCES Tickets (TicketId)
      LABEL BLOCKS,
    TicketCauses
      SOURCE KEY (CauserTicketId) REFERENCES Tickets (TicketId)
      DESTINATION KEY (CausedTicketId) REFERENCES Tickets (TicketId)
      LABEL CAUSES
  );
