/**
 * PRODUCTION-READY Resume Upload Component
 * Handles file upload with validation, progress tracking, and error handling
 */
import React, { useState } from 'react';
import { Upload, CheckCircle, XCircle, Loader2, FileText, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';

interface UploadResponse {
  status: string;
  filename: string;
  file_path: string;
  text_length: number;
  summary?: string;
}

interface UploadError {
  message: string;
  details?: string;
}

const ResumeUpload: React.FC = () => {
  // State management
  const [file, setFile] = useState<File | null>(null);
  const [email, setEmail] = useState<string>('');
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadSuccess, setUploadSuccess] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<UploadError | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);

  // Validation constants
  const ALLOWED_TYPES = ['.pdf', '.docx', '.txt'];
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  /**
   * Validate file before upload
   */
  const validateFile = (file: File): { valid: boolean; error?: string } => {
    // Check file type
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_TYPES.includes(fileExtension)) {
      return {
        valid: false,
        error: `Invalid file type. Please upload ${ALLOWED_TYPES.join(', ')} files only.`
      };
    }

    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return {
        valid: false,
        error: `File too large. Maximum size is ${MAX_FILE_SIZE / 1024 / 1024}MB.`
      };
    }

    return { valid: true };
  };

  /**
   * Handle file selection
   */
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    
    // Reset states
    setUploadError(null);
    setUploadSuccess(false);
    setUploadResult(null);
    setUploadProgress(0);

    if (!selectedFile) {
      setFile(null);
      return;
    }

    // Validate file
    const validation = validateFile(selectedFile);
    if (!validation.valid) {
      setUploadError({ message: validation.error || 'Invalid file' });
      setFile(null);
      return;
    }

    setFile(selectedFile);
  };

  /**
   * Handle email input
   */
  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value);
    setUploadError(null);
  };

  /**
   * Upload resume to backend
   */
  const handleUpload = async () => {
    // Validation
    if (!file) {
      setUploadError({ message: 'Please select a file to upload' });
      return;
    }

    if (!email || !email.includes('@')) {
      setUploadError({ message: 'Please enter a valid email address' });
      return;
    }

    // Reset states
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(false);
    setUploadProgress(0);
    setUploadResult(null);

    try {
      // Create FormData (CRITICAL for file uploads)
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_email', email);

      console.log('📤 Uploading resume:', {
        filename: file.name,
        size: file.size,
        type: file.type,
        email: email
      });

      // Simulate progress (real progress requires XHR or custom fetch)
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90));
      }, 200);

      // Upload with fetch (supports FormData)
      const response = await fetch(`${API_BASE_URL}/api/upload-resume`, {
        method: 'POST',
        body: formData, // Do NOT set Content-Type header - browser will set it with boundary
      });

      clearInterval(progressInterval);
      setUploadProgress(100);

      // Check response
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || 
          errorData.message || 
          `Upload failed with status ${response.status}`
        );
      }

      // Parse success response
      const data: UploadResponse = await response.json();
      
      console.log('✅ Upload successful:', data);

      setUploadResult(data);
      setUploadSuccess(true);
      
      // Clear form after success
      setTimeout(() => {
        setFile(null);
        setEmail('');
        if (document.getElementById('resume-file') as HTMLInputElement) {
          (document.getElementById('resume-file') as HTMLInputElement).value = '';
        }
      }, 2000);

    } catch (error: any) {
      console.error('❌ Upload error:', error);
      
      // Determine error type for better user feedback
      let errorMessage = 'Upload failed';
      let errorDetails = error.message || 'An unexpected error occurred';
      
      if (error.message === 'Failed to fetch' || error.name === 'TypeError') {
        errorMessage = 'Cannot connect to server';
        errorDetails = `Backend server at ${API_BASE_URL} is not responding. Please ensure:
1. Backend is running (check http://localhost:8000/api/health)
2. Frontend .env has correct VITE_API_BASE_URL
3. No firewall or CORS issues`;
      } else if (error.message.includes('CORS')) {
        errorMessage = 'CORS Error';
        errorDetails = 'Backend server is not allowing requests from this origin. Check CORS_ORIGINS configuration.';
      } else if (error.message.includes('Network')) {
        errorMessage = 'Network Error';
        errorDetails = 'Please check your internet connection and try again.';
      }
      
      setUploadError({
        message: errorMessage,
        details: errorDetails
      });
      setUploadProgress(0);
    } finally {
      setUploading(false);
    }
  };

  /**
   * Reset form
   */
  const handleReset = () => {
    setFile(null);
    setEmail('');
    setUploadError(null);
    setUploadSuccess(false);
    setUploadResult(null);
    setUploadProgress(0);
    if (document.getElementById('resume-file') as HTMLInputElement) {
      (document.getElementById('resume-file') as HTMLInputElement).value = '';
    }
  };

  return (
    <Card className="w-full max-w-2xl mx-auto glass">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="w-6 h-6 text-primary" />
          Upload Your Resume
        </CardTitle>
        <CardDescription>
          Upload your resume (PDF, DOCX, or TXT) for AI-powered parsing and job matching
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Email Input */}
        <div className="space-y-2">
          <Label htmlFor="user-email">Email Address</Label>
          <Input
            id="user-email"
            type="email"
            placeholder="your.email@example.com"
            value={email}
            onChange={handleEmailChange}
            disabled={uploading}
            className="w-full"
          />
        </div>

        {/* File Input */}
        <div className="space-y-2">
          <Label htmlFor="resume-file">Resume File</Label>
          <div className="flex items-center gap-4">
            <Input
              id="resume-file"
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={handleFileChange}
              disabled={uploading}
              className="flex-1"
            />
            {file && (
              <span className="text-sm text-muted-foreground">
                {(file.size / 1024).toFixed(1)} KB
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Supported formats: PDF, DOCX, TXT (Max: 10MB)
          </p>
        </div>

        {/* Upload Progress */}
        {uploading && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>Uploading...</span>
              <span>{uploadProgress}%</span>
            </div>
            <Progress value={uploadProgress} className="w-full" />
          </div>
        )}

        {/* Error Alert */}
        {uploadError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <strong>{uploadError.message}</strong>
              {uploadError.details && (
                <p className="mt-1 text-sm">{uploadError.details}</p>
              )}
            </AlertDescription>
          </Alert>
        )}

        {/* Success Alert */}
        {uploadSuccess && uploadResult && (
          <Alert className="border-green-500 bg-green-50 dark:bg-green-950">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800 dark:text-green-200">
              <strong>Resume uploaded successfully!</strong>
              <div className="mt-2 space-y-1 text-sm">
                <p>📄 File: {uploadResult.filename}</p>
                <p>📝 Extracted: {uploadResult.text_length} characters</p>
                {uploadResult.summary && (
                  <p className="mt-2 p-2 bg-white dark:bg-gray-900 rounded">
                    {uploadResult.summary}
                  </p>
                )}
              </div>
            </AlertDescription>
          </Alert>
        )}

        {/* Action Buttons */}
        <div className="flex gap-4">
          <Button
            onClick={handleUpload}
            disabled={!file || !email || uploading}
            className="flex-1"
          >
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4 mr-2" />
                Upload Resume
              </>
            )}
          </Button>

          {(file || uploadSuccess) && (
            <Button
              onClick={handleReset}
              variant="outline"
              disabled={uploading}
            >
              Reset
            </Button>
          )}
        </div>

        {/* Info Box */}
        <div className="p-4 bg-muted rounded-lg space-y-2">
          <h4 className="font-semibold text-sm">What happens next?</h4>
          <ul className="text-sm space-y-1 text-muted-foreground">
            <li>✅ AI extracts your skills, experience, and education</li>
            <li>✅ Resume is parsed for job matching</li>
            <li>✅ Profile is ready for automatic job applications</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
};

export default ResumeUpload;
