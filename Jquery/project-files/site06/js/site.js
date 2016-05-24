$(function(){
	$("li").has(".dropdown").hover(
		function() {
			$(this).find(".dropdown").slideDown();
		},
		function() {
			$(this).find(".dropdown").slideUp();
		}
	);
});