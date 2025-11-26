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

    public partial class DepartmentSP : DbMigration
    {
        public override void Up()
        {
            CreateStoredProcedure(
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

                      SELECT t0.[DepartmentID]
                      FROM [dbo].[Department] AS t0
                      WHERE @@ROWCOUNT > 0 AND t0.[DepartmentID] = @DepartmentID"
            );

            CreateStoredProcedure(
                "dbo.Department_Update",
                p => new
                    {
                        DepartmentID = p.Int(),
                        Name = p.String(maxLength: 50),
                        Budget = p.Decimal(precision: 19, scale: 4, storeType: "money"),
                        StartDate = p.DateTime(),
                        InstructorID = p.Int(),
                    },
                body:
                    @"UPDATE [dbo].[Department]
                      SET [Name] = @Name, [Budget] = @Budget, [StartDate] = @StartDate, [InstructorID] = @InstructorID
                      WHERE ([DepartmentID] = @DepartmentID)"
            );

            CreateStoredProcedure(
                "dbo.Department_Delete",
                p => new
                    {
                        DepartmentID = p.Int(),
                    },
                body:
                    @"DELETE [dbo].[Department]
                      WHERE ([DepartmentID] = @DepartmentID)"
            );

        }

        public override void Down()
        {
            DropStoredProcedure("dbo.Department_Delete");
            DropStoredProcedure("dbo.Department_Update");
            DropStoredProcedure("dbo.Department_Insert");
        }
    }
}
