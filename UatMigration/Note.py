#large number of record deletion logic for future use
    def delete_archived_student_scheduler(self):
            # Define the date 30 days ago
            days =30
            delete_older_records = fields.Datetime.now() - timedelta(days=days)
            
            # Search for inactive students whose write_date is greater than 30 days ago
            student_ids = self.env['student.student'].search([
                ('active', '=', False),
                ('write_date', '<', delete_older_records)
            ])
            
            AllstudentId = student_ids.ids if student_ids else []
            
            # If no student records to delete, exit early
            if not AllstudentId:
                _logger.info('No inactive students found for deletion.')
                return

            # Define delete configurations (tables to be affected and their corresponding column)
            delete_config = [
                {'table': 'simulab_student_dashboard', 'column': 'student_id'},
                {'table': 'student_quiz_answer', 'column': 'student_id'},
                {'table': 'student_quiz_question', 'column': 'student_id'},
                {'table': 'student_experiment', 'column': 'student_id'},
                {'table': 'student_experiment_quiz', 'column': 'student_id'},
                {'table': 'enrolled_course', 'column': 'student_id'},
                {'table': 'class_student_rel', 'column': 'student_id'},
                {'table': 'ir_attachment', 'column': 'res_id', 'subquery': """
                    SELECT ID FROM res_users WHERE login IN (
                        SELECT login FROM student_student WHERE id IN %s
                    )
                """},
                {'table': 'res_groups_users_rel', 'column': 'uid', 'subquery': """
                 SELECT ID FROM res_users WHERE login IN (
                    SELECT login FROM student_student WHERE id IN %s
                 )
                """},
                {'table': 'res_users', 'column': 'login', 'subquery': """
                    SELECT login FROM student_student WHERE id IN %s
                """},
                {'table': 'student_student', 'column': 'id'}
            ]

            # Disable foreign key constraints temporarily
            self._cr.execute("SET session_replication_role = replica;")

            retries = 0
            MAX_RETRIES = 3
            RETRY_DELAY = 1  # seconds

            while retries < MAX_RETRIES:
                try:
                    # Start transaction and delete in batches
                    for table_config in delete_config:
                        table_name = table_config['table']
                        column_name = table_config['column']
                        subquery = table_config.get('subquery', None)
                        batch_size = 1000  # Process records in batches of 1000

                        # Initialize counter for records deleted from each table
                        deleted_count = 0

                        # Handle deletion with a subquery (for attachments and res_users)
                        if subquery:
                            for i in range(0, len(AllstudentId), batch_size):
                                batch_ids = AllstudentId[i:i + batch_size]
                                self._cr.execute(f"""
                                    DELETE FROM {table_name}
                                    WHERE {column_name} IN ({subquery})
                                """, (tuple(batch_ids),))
                                # Count the number of rows deleted
                                deleted_count += self._cr.rowcount
                        else:
                            # Perform batch deletion without subquery
                            for i in range(0, len(AllstudentId), batch_size):
                                batch_ids = AllstudentId[i:i + batch_size]
                                self._cr.execute(f"""
                                    DELETE FROM {table_name}
                                    WHERE {column_name} IN %s
                                """, (tuple(batch_ids),))
                                # Count the number of rows deleted
                                deleted_count += self._cr.rowcount

                        # Log the number of records deleted for each table
                        _logger.info(f"Deleted {deleted_count} records from table {table_name}.")
                        print(f"Deleted {deleted_count} records from table {table_name}.")

                    # Commit the transaction if all operations are successful
                    self._cr.commit()
                    break  # Exit the loop if successful

                except SerializationFailure as e:
                    # If a serialization failure occurs, retry the operation
                    retries += 1
                    _logger.warning(f"Serialization failure occurred, retrying... Attempt {retries}/{MAX_RETRIES}")
                    if retries >= MAX_RETRIES:
                        # If maximum retries are reached, raise the error
                        self._cr.rollback()
                        _logger.error("Max retries reached. Could not complete the delete operation.")
                        raise e
                    else:
                        # Rollback and retry after a short delay
                        self._cr.rollback()
                        time.sleep(RETRY_DELAY)
                except Exception as e:
                    # Rollback for any other exception
                    self._cr.rollback()
                    _logger.error(f"An error occurred: {str(e)}")
                    raise e

            # Re-enable foreign key constraints after deletion
            self._cr.execute("SET session_replication_role = origin;")
            _logger.info("Foreign key constraints re-enabled after deletion process.")
