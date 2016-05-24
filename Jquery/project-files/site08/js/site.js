$(function(){
	
	//----------------DROPDOWN-----------------\\
	$("li").has(".dropdown").hover(
		function() {
			$(this).find(".dropdown").slideDown();
		},
		function() {
			$(this).find(".dropdown").slideUp();
		}
	);
	
	//---------------THUMBNAILS-------------\\
	$(".thumbnail").animate({
		left: "400px"
	},	
	2000);
});