
function ExcelSheetAssessmentXBlock(runtime, element,server) {


    function xblock($, _) {
        var uploadUrl = runtime.handlerUrl(element, 'upload_assignment');
        var downloadUrl = runtime.handlerUrl(element, 'download_assignment');
        var qdownloadUrl = runtime.handlerUrl(element, 'download_question');




        var template = _.template($(element).find("#sga-tmpl").text());
        var gradingTemplate;



        function grading()
        {
            alert("Function grading is being called");
            //var gradinga= runtime.handlerUrl(element,'grade_this_guy');
/*
            $.ajax({
                type: "POST",
                url: gradinga,
                data: JSON.stringify({"hello": "world"}),
                success :function fun(){ alert("hi");}
                error : alert("error");
            });
*/        
       }

        function render(state) {



            // Add download urls to template context
            state.downloadUrl = downloadUrl;
	 //   state.grading = grading;
            state.qdownloadUrl = qdownloadUrl;
    //        state.annotatedUrl = annotatedUrl;
            state.error = state.error || false;

            // Render template
            var content = $(element).find('#sga-content').html(template(state));

            // Set up file upload
            var fileUpload = $(content).find('.fileupload').fileupload({
                url: uploadUrl,
                add: function(e, data) {
                    var do_upload = $(content).find('.upload').html('');
                    $(content).find('p.error').html('');
                    $('<button/>')
                        .text('Upload ' + data.files[0].name)
                        .appendTo(do_upload)
                        .click(function() {
                            do_upload.text('Uploading...');
                            var block = $(element).find(".test1_xblock");
                            var data_max_size = block.attr("data-max-size");
                            var size = data.files[0].size;
                            if (!_.isUndefined(size)) {
                                //if file size is larger max file size define in env(django)
                                if (size >= data_max_size) {
                                    state.error = 'The file you are trying to upload is too large.';
                                    render(state);
                                    return;
                                }
                            }
                            data.submit();
                        });
                },
                progressall: function(e, data) {
                    var percent = parseInt(data.loaded / data.total * 100, 10);
                    $(content).find('.upload').text(
                        'Uploading... ' + percent + '%');
                },
                fail: function(e, data) {
                    /**
                     * Nginx and other sanely implemented servers return a
                     * "413 Request entity too large" status code if an
                     * upload exceeds its limit.  See the 'done' handler for
                     * the not sane way that Django handles the same thing.
                     */
                    if (data.jqXHR.status === 413) {
                        /* I guess we have no way of knowing what the limit is
                         * here, so no good way to inform the user of what the
                         * limit is.
                         */
                        state.error = 'The file you are trying to upload is too large.';
                    } else {
                        // Suitably vague
                        state.error = 'There was an error uploading your file.';

                        // Dump some information to the console to help someone
                        // debug.
                        console.log('There was an error with file upload.');
                        console.log('event: ', e);
                        console.log('data: ', data);
                    }
                    render(state);
                },
                done: function(e, data) {
                    /* When you try to upload a file that exceeds Django's size
                     * limit for file uploads, Django helpfully returns a 200 OK
                     * response with a JSON payload of the form:
                     *
                     *   {'success': '<error message'}
                     *
                     * Thanks Obama!
                     */
                    if (data.result.success !== undefined) {
                        // Actually, this is an error
                        state.error = data.result.success;
                        render(state);
                    } else {
                        // The happy path, no errors
                        render(data.result);
                    }
                }
            });

            updateChangeEvent(fileUpload);
        }



        function updateChangeEvent(fileUploadObj) {
            fileUploadObj.off('change').on('change', function (e) {
                var that = $(this).data('blueimpFileupload'),
                    data = {
                        fileInput: $(e.target),
                        form: $(e.target.form)
                    };

                that._getFileInputFiles(data.fileInput).always(function (files) {
                    data.files = files;
                    if (that.options.replaceFileInput) {
                        that._replaceFileInput(data.fileInput);
                    }
                    that._onAdd(e, data);
                });
            });
        }

        $(function($) { // onLoad

            var block = $(element).find('.test1_block');
            var state = block.attr('data-state');
            render(JSON.parse(state));
//                    var grading= runtime.handlerUrl(element,'rungrader');
            $('.grademyassignment', element).click(function(eventObject) {
                 alert("alert");
                 grading();
            });

        });
    }

    function loadjs(url) {
        $('<script>')
            .attr('type', 'text/javascript')
            .attr('src', url)
            .appendTo(element);
    }

    if (require === undefined) {
        /**
         * The LMS does not use require.js (although it loads it...) and
         * does not already load jquery.fileupload.  (It looks like it uses
         * jquery.ajaxfileupload instead.  But our XBlock uses
         * jquery.fileupload.
         */
        loadjs('/static/js/vendor/jQuery-File-Upload/js/jquery.iframe-transport.js');
        loadjs('/static/js/vendor/jQuery-File-Upload/js/jquery.fileupload.js');
        xblock($, _);
    } else {
        /**
         * Studio, on the other hand, uses require.js and already knows about
         * jquery.fileupload.
         */
        require(['jquery', 'underscore', 'jquery.fileupload'], xblock);
    }

  

}
	

