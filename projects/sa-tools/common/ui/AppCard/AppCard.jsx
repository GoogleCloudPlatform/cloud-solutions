/*
 * Copyright 2023 Google LLC
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
 * limitations under the License.
 */

import React from 'react';
import { Card, Chip } from '@mui/material';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';

/**
 * AppCard functional component
 * that displays single Application Card
 * @return {!AppCard}
 */
function AppCard({ item }) {
  return (
    <>
      <Card
        className="home-card"
        sx={{
          minWidth: 375,
          maxWidth: 375,
          margin: '1rem',
          position: 'relative',
          backgroundColor: `${item.disabled ? '#b4b4b4' : 'white'}`,
          cursor: 'pointer',
          borderLeft: `${
            item.disabled ? '3px solid grey' : '3px solid #0884d1'
          }`,
        }}
        onClick={() => {
          item.externalLink
            ? (window.location = `${item.externalLink}`)
            : history.push(item.link);
        }}
      >
        <CardContent style={{ display: 'flex', flexDirection: 'row' }}>
          {item.icon}
          <div>
            <Chip label={item.category} size="small" variant="outlined" />
            <Typography
              className="home-card-title"
              variant="h5"
              sx={{
                mt: 2,
                color: `${item.disabled ? '#e3e3e3' : '#0884d1'}`,
              }}
            >
              {item.name}
            </Typography>
            <Typography
              sx={{ fontSize: '0.9rem', mb: 1.4 }}
              color="text.secondary"
            >
              {item.tags}
            </Typography>
            <Typography variant="body2">
              {item.description}{' '}
              {item.externalLink ? (
                <a href={item.externalLink} target="_blank" rel="noreferrer">
                  Find out more.
                </a>
              ) : null}
            </Typography>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
export { AppCard };
