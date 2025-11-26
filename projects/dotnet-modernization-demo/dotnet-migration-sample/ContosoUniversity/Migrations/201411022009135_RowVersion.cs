/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License
 */

namespace ContosoUniversity.Migrations
{
    using System;
    using System.Data.Entity.Migrations;

    public partial class RowVersion : DbMigration
    {
        public override void Up()
        {
            AddColumn("dbo.Department", "RowVersion", c => c.Binary(nullable: false, fixedLength: true, timestamp: true, storeType: "rowversion"));
            AlterStoredProcedure(
                "dbo.Department_Insert",
                p => new
                    {
                        Name = p.String(maxLength: 50),
                        Budget = p.Decimal(precision: 19, scale: 4, storeType: "money"),
                        StartDate = p.DateTime(),
                        InstructorID = p.Int(),
                    },
                body:
                    @"INSERT [dbo].[Department]([Name], [Budget], [StartDate], [InstructorID])
                      VALUES (@Name, @Budget, @StartDate, @InstructorID)

                      DECLARE @DepartmentID int
                      SELECT @DepartmentID = [DepartmentID]
                      FROM [dbo].[Department]
                      WHERE @@ROWCOUNT > 0 AND [DepartmentID] = scope_identity()

                      SELECT t0.[DepartmentID], t0.[RowVersion]
                      FROM [dbo].[Department] AS t0
                      WHERE @@ROWCOUNT > 0 AND t0.[DepartmentID] = @DepartmentID"
            );

            AlterStoredProcedure(
                "dbo.Department_Update",
                p => new
                    {
                        DepartmentID = p.Int(),
                        Name = p.String(maxLength: 50),
                        Budget = p.Decimal(precision: 19, scale: 4, storeType: "money"),
                        StartDate = p.DateTime(),
                        InstructorID = p.Int(),
                        RowVersion_Original = p.Binary(maxLength: 8, fixedLength: true, storeType: "rowversion"),
                    },
                body:
                    @"UPDATE [dbo].[Department]
                      SET [Name] = @Name, [Budget] = @Budget, [StartDate] = @StartDate, [InstructorID] = @InstructorID
                      WHERE (([DepartmentID] = @DepartmentID) AND (([RowVersion] = @RowVersion_Original) OR ([RowVersion] IS NULL AND @RowVersion_Original IS NULL)))

                      SELECT t0.[RowVersion]
                      FROM [dbo].[Department] AS t0
                      WHERE @@ROWCOUNT > 0 AND t0.[DepartmentID] = @DepartmentID"
            );

            AlterStoredProcedure(
                "dbo.Department_Delete",
                p => new
                    {
                        DepartmentID = p.Int(),
                        RowVersion_Original = p.Binary(maxLength: 8, fixedLength: true, storeType: "rowversion"),
                    },
                body:
                    @"DELETE [dbo].[Department]
                      WHERE (([DepartmentID] = @DepartmentID) AND (([RowVersion] = @RowVersion_Original) OR ([RowVersion] IS NULL AND @RowVersion_Original IS NULL)))"
            );

        }

        public override void Down()
        {
            DropColumn("dbo.Department", "RowVersion");
            throw new NotSupportedException("Scaffolding create or alter procedure operations is not supported in down methods.");
        }
    }
}
