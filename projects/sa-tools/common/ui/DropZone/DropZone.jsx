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

import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { Button, Popover, Typography } from '@mui/material';
import { FileUpload } from '@mui/icons-material';

import React, { useMemo, useCallback } from 'react';

import { useDropzone } from 'react-dropzone';

const baseStyle = {
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  padding: '20px',
  borderWidth: 3,
  borderRadius: 2,
  borderColor: '#c9d0d6',
  borderStyle: 'dashed',
  backgroundColor: '#fafafa',
  color: '#3390da',
  outline: 'none',
  transition: 'border .24s ease-in-out',
};

const focusedStyle = {
  borderColor: '#2196f3',
};

const acceptStyle = {
  borderColor: '#00e676',
};

const rejectStyle = {
  borderColor: '#ff1744',
};

/**
 * StyledDropzone functional component for file upload.
 * @param {Object} props
 * @return {!StyledDropzone}
 */
function StyledDropzone(props) {
  const [filesJsx, setFilesJsx] = React.useState([]);
  // const [pdfFile, setPdfFile] = React.useState(null);

  const setValueFromChild = props.setValueFromChild;

  const onDrop = useCallback(
    async (acceptedFiles) => {
      const file = acceptedFiles[0];
      setValueFromChild(file);
      setFilesJsx(
        <li key={file.path}>
          {file.path} - {file.size} bytes
        </li>
      );
    },
    [setValueFromChild]
  );

  const { getRootProps, getInputProps, isFocused, isDragAccept, isDragReject } =
    useDropzone({
      onDrop,
      accept: { 'image/*': [], 'application/pdf': [], 'application/json': [] },
    });

  const style = useMemo(
    () => ({
      ...baseStyle,
      ...(isFocused ? focusedStyle : {}),
      ...(isDragAccept ? acceptStyle : {}),
      ...(isDragReject ? rejectStyle : {}),
    }),
    [isFocused, isDragAccept, isDragReject]
  );

  const [anchorEl, setAnchorEl] = React.useState(null);

  const open = Boolean(anchorEl);
  const id = open ? 'simple-popover' : undefined;

  const hint = (
    <div style={{ textAlign: 'center' }}>
      <HelpOutlineIcon
        style={{ fontSize: '2rem', color: '#3390da' }}
        aria-describedby={id}
        variant='contained'
        onClick={handleHelpClick}
        sx={{ mt: 2, cursor: 'pointer' }}
      />
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        onClose={handleHelpClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}>
        <Typography
          sx={{ p: 2, width: '350px' }}
          dangerouslySetInnerHTML={{ __html: props.instruction }}></Typography>
      </Popover>
    </div>
  );

  /**
   * Handles help button click
   * @param {!Event} event
   */
  function handleHelpClick(event) {
    setAnchorEl(event.currentTarget);
  }

  /**
   * Handles Help's close button click
   */
  function handleHelpClose() {
    setAnchorEl(null);
  }

  return (
    <div
      style={{
        border: '2px solid #a7bfd2',
        padding: 15,
        backgroundColor: 'white',
        fontFamily: 'Roboto!important',
        height: '280px',
      }}>
      <div {...getRootProps({ style })}>
        <input
          ref={props.fileUploadId}
          {...getInputProps()}
        />
        <p>{props.description}</p>
        <FileUpload sx={{ fontSize: '3.5rem', color: '#3390da' }} />
        <p>
          or&nbsp;&nbsp;
          <Button variant='outlined'>click</Button>&nbsp;to select file-
        </p>
      </div>
      <aside>
        <div
          style={{
            width: '100%',
            display: 'flex',
            flexDirection: 'row',
            justifyContent: 'space-between',
          }}>
          {/* {fileHeader} */}
          <ul>{filesJsx}</ul>
          {props.instruction ? hint : ''}
        </div>
      </aside>
    </div>
  );
}

export { StyledDropzone };
