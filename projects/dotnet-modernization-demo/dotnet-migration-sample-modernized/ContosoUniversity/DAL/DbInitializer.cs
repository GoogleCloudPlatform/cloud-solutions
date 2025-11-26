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

using ContosoUniversity.Models;
using System;
using System.Linq;

namespace ContosoUniversity.DAL
{
    public static class DbInitializer
    {
        public static void Initialize(SchoolContext context)
        {
            context.Database.EnsureCreated();

            // Look for any students.
            if (context.Students.Any())
            {
                return;   // DB has been seeded
            }

            var students = new Student[]
            {
                new Student{FirstMidName="Carson",LastName="Alexander",EnrollmentDate=DateTime.Parse("2005-09-01").ToUniversalTime()},
                new Student{FirstMidName="Meredith",LastName="Alonso",EnrollmentDate=DateTime.Parse("2002-09-01").ToUniversalTime()},
                new Student{FirstMidName="Arturo",LastName="Anand",EnrollmentDate=DateTime.Parse("2003-09-01").ToUniversalTime()},
                new Student{FirstMidName="Gytis",LastName="Barzdukas",EnrollmentDate=DateTime.Parse("2002-09-01").ToUniversalTime()},
                new Student{FirstMidName="Yan",LastName="Li",EnrollmentDate=DateTime.Parse("2002-09-01").ToUniversalTime()},
                new Student{FirstMidName="Peggy",LastName="Justice",EnrollmentDate=DateTime.Parse("2001-09-01").ToUniversalTime()},
                new Student{FirstMidName="Laura",LastName="Norman",EnrollmentDate=DateTime.Parse("2003-09-01").ToUniversalTime()},
                new Student{FirstMidName="Nino",LastName="Olivetto",EnrollmentDate=DateTime.Parse("2005-09-01").ToUniversalTime()}
            };
            foreach (Student s in students)
            {
                context.Students.Add(s);
            }
            context.SaveChanges();
            var savedStudents = context.Students.ToList();

            var instructors = new Instructor[]
            {
                new Instructor { FirstMidName = "Kim",     LastName = "Abercrombie", HireDate = DateTime.Parse("1995-03-11").ToUniversalTime() },
                new Instructor { FirstMidName = "Fadi",    LastName = "Fakhouri",    HireDate = DateTime.Parse("2002-07-06").ToUniversalTime() },
                new Instructor { FirstMidName = "Roger",   LastName = "Harui",       HireDate = DateTime.Parse("1998-07-01").ToUniversalTime() },
                new Instructor { FirstMidName = "Candace", LastName = "Kapoor",      HireDate = DateTime.Parse("2001-01-15").ToUniversalTime() },
                new Instructor { FirstMidName = "Roger",   LastName = "Zheng",       HireDate = DateTime.Parse("2004-02-12").ToUniversalTime() }
            };
            foreach (Instructor i in instructors)
            {
                context.Instructors.Add(i);
            }
            context.SaveChanges();
            var savedInstructors = context.Instructors.ToList();

            var departments = new Department[]
            {
                new Department{Name="English", Budget=350000, StartDate=DateTime.Parse("2007-09-01").ToUniversalTime(), InstructorID=savedInstructors[0].ID},
                new Department{Name="Mathematics", Budget=100000, StartDate=DateTime.Parse("2007-09-01").ToUniversalTime(), InstructorID=savedInstructors[1].ID},
                new Department{Name="Engineering", Budget=350000, StartDate=DateTime.Parse("2007-09-01").ToUniversalTime(), InstructorID=savedInstructors[2].ID},
                new Department{Name="Economics", Budget=100000, StartDate=DateTime.Parse("2007-09-01").ToUniversalTime(), InstructorID=savedInstructors[3].ID}
            };
            foreach (Department d in departments)
            {
                context.Departments.Add(d);
            }
            context.SaveChanges();
            var savedDepartments = context.Departments.ToList();

            var courses = new Course[]
            {
                new Course{CourseID=1050,Title="Chemistry",Credits=3, DepartmentID=savedDepartments[2].DepartmentID},
                new Course{CourseID=4022,Title="Microeconomics",Credits=3, DepartmentID=savedDepartments[3].DepartmentID},
                new Course{CourseID=4041,Title="Macroeconomics",Credits=3, DepartmentID=savedDepartments[3].DepartmentID},
                new Course{CourseID=1045,Title="Calculus",Credits=4, DepartmentID=savedDepartments[1].DepartmentID},
                new Course{CourseID=3141,Title="Trigonometry",Credits=4, DepartmentID=savedDepartments[1].DepartmentID},
                new Course{CourseID=2021,Title="Composition",Credits=3, DepartmentID=savedDepartments[0].DepartmentID},
                new Course{CourseID=2042,Title="Literature",Credits=4, DepartmentID=savedDepartments[0].DepartmentID}
            };
            foreach (Course c in courses)
            {
                context.Courses.Add(c);
            }
            context.SaveChanges();
            var savedCourses = context.Courses.ToList();

            var enrollments = new Enrollment[]
            {
                new Enrollment{StudentID=savedStudents[0].ID,CourseID=savedCourses[0].CourseID,Grade=Grade.A},
                new Enrollment{StudentID=savedStudents[0].ID,CourseID=savedCourses[1].CourseID,Grade=Grade.C},
                new Enrollment{StudentID=savedStudents[0].ID,CourseID=savedCourses[2].CourseID,Grade=Grade.B},
                new Enrollment{StudentID=savedStudents[1].ID,CourseID=savedCourses[3].CourseID,Grade=Grade.B},
                new Enrollment{StudentID=savedStudents[1].ID,CourseID=savedCourses[4].CourseID,Grade=Grade.F},
                new Enrollment{StudentID=savedStudents[1].ID,CourseID=savedCourses[5].CourseID,Grade=Grade.F},
                new Enrollment{StudentID=savedStudents[2].ID,CourseID=savedCourses[0].CourseID},
                new Enrollment{StudentID=savedStudents[3].ID,CourseID=savedCourses[0].CourseID},
                new Enrollment{StudentID=savedStudents[3].ID,CourseID=savedCourses[1].CourseID,Grade=Grade.F},
                new Enrollment{StudentID=savedStudents[4].ID,CourseID=savedCourses[2].CourseID,Grade=Grade.C},
                new Enrollment{StudentID=savedStudents[5].ID,CourseID=savedCourses[3].CourseID},
                new Enrollment{StudentID=savedStudents[6].ID,CourseID=savedCourses[4].CourseID,Grade=Grade.A}
            };
            foreach (Enrollment e in enrollments)
            {
                context.Enrollments.Add(e);
            }
            context.SaveChanges();
        }
    }
}
